from django.contrib import admin
from .models import CashClosure, CashClosureItem, BankTransaction

class CashClosureItemInline(admin.TabularInline):
    model = CashClosureItem
    extra = 1

@admin.register(CashClosure)
class CashClosureAdmin(admin.ModelAdmin):
    list_display = ('date', 'operator', 'contanti', 'pag_pos', 'totale_generale')
    list_filter = ('date', 'operator')
    search_fields = ('operator',)
    inlines = [CashClosureItemInline]

@admin.register(BankTransaction)
class BankTransactionAdmin(admin.ModelAdmin):
    list_display = ('date', 'transaction_type', 'amount', 'description')
    list_filter = ('date', 'transaction_type')

