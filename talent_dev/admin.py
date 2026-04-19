from django.contrib import admin
from .models import TraitDictionaryProxy, RoleSynergyMasterProxy, PersonalityTestProxy, PersonalityIndicatorProxy
from simple_history.admin import SimpleHistoryAdmin

@admin.register(TraitDictionaryProxy)
class TraitDictionaryAdmin(admin.ModelAdmin):
    list_display = ('trait_name',)
    search_fields = ('trait_name',)

@admin.register(RoleSynergyMasterProxy)
class RoleSynergyMasterAdmin(admin.ModelAdmin):
    list_display = ('position_name', 'ideal_primary_traits', 'warning_primary_traits')
    search_fields = ('position_name',)

@admin.register(PersonalityTestProxy)
class PersonalityTestAdmin(SimpleHistoryAdmin):
    list_display = ('employee', 'primary_trait', 'synergy_score', 'test_date')
    search_fields = ('employee__full_name', 'primary_trait', 'secondary_trait')
    list_filter = ('primary_trait', 'test_date')
    readonly_fields = ('sanguine_score', 'melancholic_score', 'choleric_score', 'phlegmatic_score',
                       'honesty_score', 'responsibility_score',
                       'sanguine_maturity', 'melancholic_maturity', 'choleric_maturity', 'phlegmatic_maturity',
                       'primary_trait', 'secondary_trait', 'synergy_score')

@admin.register(PersonalityIndicatorProxy)
class PersonalityIndicatorAdmin(admin.ModelAdmin):
    list_display = ('indicator_text', 'category', 'kind', 'weight', 'is_active')
    list_filter = ('category', 'kind', 'is_active')
    search_fields = ('indicator_text',)
    list_editable = ('weight', 'is_active')
