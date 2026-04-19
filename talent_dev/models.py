from attendance.models import TraitDictionary, RoleSynergyMaster, PersonalityTest, PersonalityIndicator

class TraitDictionaryProxy(TraitDictionary):
    class Meta:
        proxy = True
        verbose_name = "Kamus Tipe Karakter"
        verbose_name_plural = "Kamus Tipe Karakter"

class RoleSynergyMasterProxy(RoleSynergyMaster):
    class Meta:
        proxy = True
        verbose_name = "Pemetaan Sinergi Posisi"
        verbose_name_plural = "Pemetaan Sinergi Posisi"

class PersonalityTestProxy(PersonalityTest):
    class Meta:
        proxy = True
        verbose_name = "Hasil Psikotes (Talent Dev)"
        verbose_name_plural = "Hasil Psikotes (Talent Dev)"

class PersonalityIndicatorProxy(PersonalityIndicator):
    class Meta:
        proxy = True
        verbose_name = "Kamus Sub-Karakter (Form Builder)"
        verbose_name_plural = "Kamus Sub-Karakter (Form Builder)"
