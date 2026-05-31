from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class Company(models.Model):
    denominazione = models.CharField(max_length=200, verbose_name='Denominazione')
    indirizzo = models.TextField(blank=True, verbose_name='Indirizzo')
    piva = models.CharField(max_length=16, blank=True, verbose_name='PIVA')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Azienda'
        verbose_name_plural = 'Aziende'
        ordering = ['denominazione', 'id']

    def __str__(self):
        return self.denominazione or f'Azienda #{self.pk}'


class CompanyMembership(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='company_memberships')
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='memberships')

    class Meta:
        unique_together = [('user', 'company')]
        verbose_name = 'Appartenenza azienda'
        verbose_name_plural = 'Appartenenze azienda'

    def __str__(self):
        return f'{self.user.username} → {self.company}'


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    sidebar_menu = models.JSONField(default=list, blank=True, verbose_name='Menu laterale')
    ai_acquisition_provider = models.CharField(
        max_length=16,
        blank=True,
        default='',
        verbose_name='Modello IA acquisizione (preferenza operatore)',
    )

    class Meta:
        verbose_name = 'Profilo utente'
        verbose_name_plural = 'Profili utente'

    def __str__(self):
        return f'Profilo {self.user.username}'


class CashClosure(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='closures', verbose_name='Azienda')
    date = models.DateField(default=timezone.now, verbose_name="Data Chiusura")
    operator = models.CharField(max_length=100, verbose_name="Operatore")
    submitted_by = models.CharField(max_length=100, blank=True, verbose_name="Inviato da")
    
    # Summary Fields
    contanti = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Contanti")
    pag_pos = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Pag.Pos")
    cassa_auto = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Cassa Auto")
    reso_cont = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Reso Cont.")
    reso_auto = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Reso Auto")
    distrib = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Distrib.")
    totale_generale = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="TOTALE")
    totale_cassetto = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Totale Cassetto")
    differenza = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Differenza")
    
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


class CashClosureImage(models.Model):
    closure = models.ForeignKey(CashClosure, related_name='images', on_delete=models.CASCADE, verbose_name="Chiusura Cassa")
    image = models.ImageField(upload_to='closures/%Y/%m/', verbose_name="Foto Incasso")
    source = models.CharField(max_length=30, blank=True, verbose_name="Origine")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Foto Incasso"
        verbose_name_plural = "Foto Incasso"
        ordering = ['created_at']

    def __str__(self):
        return f"Foto chiusura {self.closure_id}"

class Department(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='departments', verbose_name='Azienda')
    name = models.CharField(max_length=150, verbose_name="Nome Reparto")

    class Meta:
        ordering = ['name']
        verbose_name = 'Reparto'
        verbose_name_plural = 'Reparti'
        unique_together = [('company', 'name')]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        self.name = (self.name or '').strip().upper()
        super().save(*args, **kwargs)


class AppSetting(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='settings', verbose_name='Azienda')
    key = models.CharField(max_length=100)
    value = models.TextField(blank=True)

    class Meta:
        verbose_name = 'Impostazione'
        verbose_name_plural = 'Impostazioni'
        unique_together = [('company', 'key')]

    def __str__(self):
        return self.key


class Versamento(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='versamenti', verbose_name='Azienda')
    date = models.DateField(verbose_name="Data Versamento")
    operator = models.CharField(max_length=100, verbose_name="Operatore")
    importo_versato = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Importo Versato")
    saldo_precedente = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Saldo Precedente")
    accantonamento = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Accantonamento Fondo Cassa")
    note = models.TextField(blank=True, verbose_name="Note")
    ricorda_promemoria = models.BooleanField(
        default=False,
        verbose_name="Ricorda come promemoria",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Versamento"
        verbose_name_plural = "Versamenti"
        ordering = ['-date', '-created_at']

    def __str__(self):
        return f"Versamento {self.date.strftime('%d/%m/%Y')} — € {self.importo_versato} ({self.operator})"


class MovimentoCassa(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='movimenti_cassa', verbose_name='Azienda')
    TIPO_ENTRATA = 'ENTRATA'
    TIPO_USCITA = 'USCITA'
    TIPO_CHOICES = [
        (TIPO_ENTRATA, 'Entrata'),
        (TIPO_USCITA, 'Uscita'),
    ]

    date = models.DateField(verbose_name="Data Movimento")
    operator = models.CharField(max_length=100, verbose_name="Operatore")
    tipo = models.CharField(max_length=10, choices=TIPO_CHOICES, verbose_name="Tipo")
    importo = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Importo")
    saldo_precedente = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Saldo Precedente")
    note = models.TextField(blank=True, verbose_name="Note")
    ricorda_promemoria = models.BooleanField(
        default=False,
        verbose_name="Ricorda come promemoria",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Movimento Cassa"
        verbose_name_plural = "Movimenti Cassa"
        ordering = ['-date', '-created_at']

    def __str__(self):
        segno = '+' if self.tipo == self.TIPO_ENTRATA else '-'
        return f"Movimento {self.date.strftime('%d/%m/%Y')} — {segno}€ {self.importo} ({self.operator})"


class FondoCassaMovimento(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='fondo_movimenti', verbose_name='Azienda')
    TIPO_ENTRATA = 'ENTRATA'
    TIPO_USCITA = 'USCITA'
    TIPO_CHOICES = [
        (TIPO_ENTRATA, 'Entrata'),
        (TIPO_USCITA, 'Uscita'),
    ]

    date = models.DateField(verbose_name="Data")
    tipo = models.CharField(max_length=10, choices=TIPO_CHOICES, default=TIPO_ENTRATA, verbose_name="Tipo")
    importo = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Importo")
    descrizione = models.CharField(max_length=200, blank=True, verbose_name="Descrizione")
    versamento = models.ForeignKey(
        Versamento, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='fondo_movimenti',
        verbose_name="Versamento di origine",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Movimento Fondo Cassa"
        verbose_name_plural = "Movimenti Fondo Cassa"
        ordering = ['-date', '-created_at']

    def __str__(self):
        return f"Fondo {self.date.strftime('%d/%m/%Y')} € {self.importo}"


class AcquisitionDraft(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='acquisition_drafts', verbose_name='Azienda')
    STATUS_CHOICES = [
        ('pending', 'Da verificare'),
        ('completed', 'Registrata'),
        ('cancelled', 'Annullata'),
    ]

    source = models.CharField(max_length=30, default='telegram', verbose_name="Origine")
    operator = models.CharField(max_length=100, blank=True, verbose_name="Operatore")
    telegram_chat_id = models.CharField(max_length=64, blank=True, verbose_name="Chat Telegram")
    totale_scassettato = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Totale Scassettato")
    pag_pos_reale = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        verbose_name="Totale POS reale (Telegram)",
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name="Stato")
    extracted_payload = models.JSONField(null=True, blank=True, verbose_name="Risultato estrazione IA")
    extracted_provider = models.CharField(max_length=20, blank=True, default='', verbose_name="Provider IA estrazione")
    extracted_at = models.DateTimeField(null=True, blank=True, verbose_name="Estrazione IA il")
    viewed_at = models.DateTimeField(null=True, blank=True, verbose_name="Vista in app il")
    telegram_reminder_sent_at = models.DateTimeField(null=True, blank=True, verbose_name="Promemoria Telegram il")
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Bozza Acquisizione"
        verbose_name_plural = "Bozze Acquisizione"

    def __str__(self):
        return f"Bozza {self.source} {self.created_at:%d/%m/%Y %H:%M}"


class AcquisitionDraftImage(models.Model):
    draft = models.ForeignKey(AcquisitionDraft, related_name='images', on_delete=models.CASCADE)
    image = models.ImageField(upload_to='drafts/%Y/%m/', verbose_name="Foto")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Foto Bozza"
        verbose_name_plural = "Foto Bozza"


class PushSubscription(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='push_subscriptions')
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='push_subscriptions')
    endpoint = models.TextField()
    p256dh = models.CharField(max_length=255)
    auth = models.CharField(max_length=64)
    user_agent = models.CharField(max_length=255, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Sottoscrizione Push'
        verbose_name_plural = 'Sottoscrizioni Push'
        unique_together = [('user', 'endpoint')]

    def __str__(self):
        return f'Push {self.user.username} @ {self.company.denominazione}'


class BankTransaction(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='bank_transactions', verbose_name='Azienda')
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
