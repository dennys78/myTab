from django.contrib import admin
from .models import (
    BankTransaction,
    CashClosure,
    CashClosureItem,
    Cliente,
    Company,
    CompanyMembership,
    Ricevuta,
    RicevutaRiga,
    ValoreBollato,
)

class CashClosureItemInline(admin.TabularInline):
    model = CashClosureItem
    extra = 1

@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ('denominazione', 'piva', 'created_at')
    search_fields = ('denominazione', 'piva')

@admin.register(CompanyMembership)
class CompanyMembershipAdmin(admin.ModelAdmin):
    list_display = ('user', 'company')
    list_filter = ('company',)

@admin.register(CashClosure)
class CashClosureAdmin(admin.ModelAdmin):
    list_display = ('date', 'operator', 'contanti', 'pag_pos', 'totale_generale')
    list_filter = ('date', 'operator')
    search_fields = ('operator',)
    inlines = [CashClosureItemInline]

@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    list_display = ('ragione_sociale', 'cf_piva', 'email', 'company')
    search_fields = ('ragione_sociale', 'cf_piva', 'email')
    list_filter = ('company',)


@admin.register(ValoreBollato)
class ValoreBollatoAdmin(admin.ModelAdmin):
    list_display = ('descrizione', 'importo', 'company')
    search_fields = ('descrizione',)
    list_filter = ('company',)


class RicevutaRigaInline(admin.TabularInline):
    model = RicevutaRiga
    extra = 0


@admin.register(Ricevuta)
class RicevutaAdmin(admin.ModelAdmin):
    list_display = ('date', 'cliente', 'operator', 'company')
    list_filter = ('company', 'date')
    inlines = [RicevutaRigaInline]


@admin.register(BankTransaction)
class BankTransactionAdmin(admin.ModelAdmin):
    list_display = ('date', 'transaction_type', 'amount', 'description')
    list_filter = ('date', 'transaction_type')

