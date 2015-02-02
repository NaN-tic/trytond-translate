# This file is part of translate module for Tryton.
# The COPYRIGHT file at the top level of this repository contains
# the full copyright notices and license terms.
from trytond.pool import Pool
from .translate import *
from .configuration import *

def register():
    Pool.register(
        Translate,
        TranslateFields,
        TranslateWizardStart,
        TranslateWizardTranslation,
        Configuration,
        module='translate', type_='model')
    Pool.register(
        TranslateWizard,
        module='translate', type_='wizard')
