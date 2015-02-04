# This file is part of translate module for Tryton.
# The COPYRIGHT file at the top level of this repository contains
# the full copyright notices and license terms.
from lxml import etree
from trytond.model import ModelView, ModelSQL, fields
from trytond.pool import Pool
from trytond.pyson import Bool, Eval, Not, PYSONEncoder
from trytond.transaction import Transaction
from trytond.wizard import Wizard, StateView, StateTransition, Button


__all__ = ['Translate', 'TranslateFields', 'TranslateWizardStart',
    'TranslateWizardTranslation', 'TranslateWizard']


class Translate(ModelSQL, ModelView):
    'Translate'
    __name__ = 'translate.translate'
    _rec_name = 'model'
    model = fields.Many2One('ir.model', 'Model', required=True)
    field_domain = fields.Function(fields.One2Many('ir.model.field', None,
        'Field Domain', depends=['model']),
            'get_field_domain')
    model_fields = fields.Many2Many('translate.translate-ir.model.field',
        'translate', 'field', 'Fields',
        domain=[
            ('id', 'in', Eval('field_domain')),
            ],
        depends=['field_domain'])
    keyword = fields.Many2One('ir.action.keyword', 'Keyword', readonly=True)

    @classmethod
    def __setup__(cls):
        super(Translate, cls).__setup__()
        cls._sql_constraints += [
            ('model_uniq', 'unique (model)', 'unique_model')
            ]
        cls._error_messages.update({
                'unique_model': 'Translate must be unique per model.',
                'not_modelsql': 'Model "%s" does not store information '
                    'to an SQL table.',
                })
        cls._buttons.update({
                'create_keyword': {
                    'invisible': Eval('keyword'),
                    },
                'remove_keyword': {
                    'invisible': ~Eval('keyword'),
                    },
                })

    @classmethod
    def validate(cls, translates):
        super(Translate, cls).validate(translates)
        for translate in translates:
            Model = Pool().get(translate.model.model)
            if not issubclass(Model, ModelSQL):
                cls.raise_user_error('not_modelsql',
                    (translate.model.rec_name,))

    @classmethod
    @ModelView.button
    def create_keyword(cls, translates):
        pool = Pool()
        Action = pool.get('ir.action.wizard')
        ModelData = pool.get('ir.model.data')
        Keyword = pool.get('ir.action.keyword')

        for translate in translates:
            if translate.keyword:
                continue
            action = Action(ModelData.get_id('translate',
                    'wizard_translate'))
            keyword = Keyword()
            keyword.keyword = 'form_action'
            keyword.model = '%s,-1' % translate.model.model
            keyword.action = action.action
            keyword.save()
            translate.keyword = keyword
            translate.save()

    @classmethod
    @ModelView.button
    def remove_keyword(cls, translates):
        pool = Pool()
        Keyword = pool.get('ir.action.keyword')
        Keyword.delete([x.keyword for x in translates if x.keyword])

    @classmethod
    def delete(cls, translates):
        cls.remove_keyword(translates)
        super(Translate, cls).delete(translates)

    @classmethod
    def get_field_domain(cls, translations, names):
        pool = Pool()
        ModelField = pool.get('ir.model.field')

        res = {'field_domain': {}}
        for translation in translations:
            if translation.model:
                Model = pool.get(translation.model.model)
                translatable_fields = []
                for f in Model._fields:
                    if getattr(Model._fields[f], 'translate', False):
                        translatable_fields.append(f)
                if translatable_fields:
                    model_fields = ModelField.search([
                            ('name', 'in', translatable_fields),
                            ('model', '=', translation.model)
                            ])
                    res['field_domain'].update({
                            translation.id: [f.id for f in model_fields]
                            })
        return res


class TranslateFields(ModelSQL):
    'Translate Fields'
    __name__ = 'translate.translate-ir.model.field'
    translate = fields.Many2One('translate.translate', 'Translate',
        required=True)
    field = fields.Many2One('ir.model.field', 'Field', required=True)


class TranslateWizardStart(ModelView):
    'Translate Wizard Start'
    __name__ = 'translate.wizard.start'
    source_lang = fields.Selection('get_lang', 'Source Language',
        required=True)
    target_lang = fields.Selection('get_lang', 'Target Language',
        required=True)
    translator = fields.Selection([
            (None, ''),
            ], 'Translator', required=True)

    @staticmethod
    def get_lang():
        Language = Pool().get('ir.lang')
        languages = Language.search([
                ('translatable', '=', True),
                ])
        return [(l.code, l.name) for l in languages]

    @staticmethod
    def default_source_lang():
        context = Transaction().context
        return context['language']

    @classmethod
    def default_translator(cls):
        translators = cls.translator.selection
        if translators:
            return translators[0][0]
        return


class TranslateWizardTranslation(ModelView):
    'Translate Wizard Translation'
    __name__ = 'translate.wizard.translation'

    @classmethod
    def __setup__(cls):
        super(TranslateWizardTranslation, cls).__setup__()
        cls._error_messages.update({
                'no_translation_found':
                    'No translation found for field %s.',
                'original': 'Original',
                'translation': 'Translation',
                'translate': 'Translate',
                })

    @classmethod
    def fields_view_get(cls, view_id=None, view_type='form'):
        pool = Pool()
        Translate = pool.get('translate.translate')

        res = super(TranslateWizardTranslation, cls).fields_view_get(view_id,
            view_type)
        fields = res['fields']

        context = Transaction().context
        encoder = PYSONEncoder()
        model = context.get('active_model', None)
        if not model:
            return res
        Model = pool.get(model)
        translates = Translate.search([('model.model', '=', model)],
            limit=1)
        if not translates:
            return res
        translate, = translates
        root = etree.fromstring(res['arch'])
        form = root.find('separator').getparent()

        xml_group = etree.SubElement(form, 'group', {
                'col': '3',
                'colspan': '4',
                })
        etree.SubElement(xml_group, 'label', {
                'id': 'label_original',
                'string': cls.raise_user_error('original',
                    raise_exception=False),
                'xalign': '0.0',
                })
        etree.SubElement(xml_group, 'label', {
                'id': 'label_translation',
                'string': cls.raise_user_error('translation',
                    raise_exception=False),
                'xalign': '0.0',
                })
        etree.SubElement(xml_group, 'label', {
                'id': 'label_translate',
                'string': cls.raise_user_error('translate',
                        raise_exception=False),
                'xalign': '0.0',
                })

        fields.update(Model.fields_get([f.name for f in
                    translate.model_fields]))
        for field in translate.model_fields:
            if fields[field.name].get('states'):
                fields[field.name]['states'] = {
                    'readonly': True,
                    'invisible': {},
                    }
            if fields[field.name].get('required'):
                fields[field.name]['required'] = False
            if fields[field.name].get('translate'):
                fields[field.name]['translate'] = False

            if fields[field.name].get('on_change'):
                fields[field.name]['on_change'] = []
            if fields[field.name].get('on_change_with'):
                fields[field.name]['on_change_with'] = []
            readonly = encoder.encode({"readonly": Not(Bool(Eval(
                            'translate_%s' % fields[field.name]['name'])))})
            fields['translation_%s' % field.name] = {
                'name': 'translation_%s' % fields[field.name],
                'type': fields[field.name]['type'],
                'string': 'Translation %s' % fields[field.name]['string'],
                'states': readonly,
                }
            fields['translate_%s' % field.name] = {
                'name': 'translate_%s' % fields[field.name],
                'type': 'boolean',
                'string': 'Translate %s' % fields[field.name]['string'],
                }
            etree.SubElement(xml_group, 'field', {
                    'name': field.name,
                    })
            etree.SubElement(xml_group, 'field', {
                    'name': 'translation_%s' % field.name,
                    })
            etree.SubElement(xml_group, 'field', {
                    'name': 'translate_%s' % field.name,
                    })

        res['arch'] = etree.tostring(root)
        res['fields'] = fields
        return res

    @classmethod
    def get_translation(cls, translator, text, source_lang, target_lang):
        if translator:
            translate = getattr(cls, 'get_translation_from_%s' % translator)
            return translate(text, source_lang, target_lang)

    @classmethod
    def default_get(cls, fields, with_rec_name=True):
        pool = Pool()
        Translation = pool.get('ir.translation')
        context = Transaction().context
        source_lang = context.get('source_lang', None)
        target_lang = context.get('target_lang', None)
        active_id = context.get('active_id', None)
        translator = context.get('translator', None)
        model = context.get('active_model', None)
        Model = pool.get(model)

        res = {}
        for field in fields:
            if field == 'id':
                continue
            if not field.startswith('translat'):
                resource = Translation.search([
                        ('name', '=', '%s,%s' % (Model.__name__, field)),
                        ('res_id', '=', active_id),
                        ('lang', '=', source_lang),
                        ], limit=1)
                if not resource:
                    cls.raise_user_error('no_translation_found',
                        error_args=(field,))
                res[field] = resource[0].value
                res['translation_%s' % field] = cls.get_translation(
                    translator, res[field], source_lang, target_lang)
            elif field.startswith('translate_'):
                res[field] = False
        return res


class TranslateWizard(Wizard):
    'Translate Wizard'
    __name__ = 'translate.wizard'
    start = StateView(
        'translate.wizard.start',
        'translate.view_translate_wizard_start', [
        Button('Cancel', 'end', 'tryton-cancel'),
        Button('Translate', 'translate', 'tryton-ok', default=True),
        ])
    translate = StateTransition()
    translation = StateView(
        'translate.wizard.translation',
        'translate.view_translate_wizard_translation', [
        Button('Cancel', 'end', 'tryton-cancel'),
        Button('Apply', 'update', 'tryton-ok', default=True),
        ])
    update = StateTransition()

    def transition_translate(self):
        context = Transaction().context
        context['source_lang'] = self.start.source_lang
        context['target_lang'] = self.start.target_lang
        context['translator'] = self.start.translator
        return 'translation'

    def transition_update(self):
        pool = Pool()
        context = Transaction().context
        model = context.get('active_model', None)
        translates = Translate.search([('model.model', '=', model)], limit=1)
        active_id = context.get('active_id', None)
        Model = pool.get(model)
        model = Model(active_id)
        if translates:
            translate, = translates
            with Transaction().set_context(
                    language=self.start.target_lang):
                data = {}
                for f in translate.model_fields:
                    if getattr(self.translation, 'translate_%s' % f.name,
                            False):
                        data[f.name] = getattr(self.translation,
                            'translation_%s' % f.name)
                Model.write([model], data)
        return 'end'
