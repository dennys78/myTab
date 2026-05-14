from django.db import models
from django.utils import timezone

class CashClosure(models.Model):
    date = models.DateField(default=timezone.now, verbose_name="Data Chiusura")
    operator = models.CharField(max_length=100, verbose_name="Operatore")
    
    # Summary Fields
    contanti = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Contanti")
    pag_pos = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Pag.Pos")
    cassa_auto = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Cassa Auto")
    reso_cont = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Reso Cont.")
    reso_auto = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Reso Auto")
    distrib = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Distrib.")
    totale_generale = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="TOTALE")
    
    image_ref = models.ImageField(upload_to='closures/%Y/%m/', null=True, blank=True, verbose_name="Immagine di Riferimento")
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Chiusura Cassa"
        verbose_name_plural = "Chiusure Cassa"
        ordering = ['-date']

    def __str__(self):
        return f"Chiusura del {self.date.strftime('%d/%m/%Y')} - {self.operator} (€ {self.totale_generale})"

class CashClosureItem(models.Model):
    closure = models.ForeignKey(CashClosure, related_name='items', on_delete=models.CASCADE, verbose_name="Chiusura Cassa")
    department_name = models.CharField(max_length=150, verbose_name="Descrizione Reparto")
    incomes = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Entrate")
    expenses = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Uscite")
    balance = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Saldo Cassa")

    class Meta:
        verbose_name = "Voce Chiusura"
        verbose_name_plural = "Voci Chiusura"

    def __str__(self):
        return f"{self.department_name} (Saldo: € {self.balance})"

class BankTransaction(models.Model):
    TRANSACTION_TYPES = [
        ('VERSAMENTO', 'Versamento Contanti'),
        ('ESTRATTO_CONTO', 'Movimento Estratto Conto'),
    ]
    date = models.DateField(verbose_name="Data Transazione")
    amount = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Importo Versato")
    description = models.TextField(verbose_name="Causale", blank=True)
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPES, verbose_name="Tipo Transazione")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Transazione Bancaria"
        verbose_name_plural = "Transazioni Bancarie"
        ordering = ['-date']

    def __str__(self):
        return f"{self.get_transaction_type_display()} del {self.date.strftime('%d/%m/%Y')} - €{self.amount}"
