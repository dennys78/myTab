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
    receive_notifications = models.BooleanField(
        default=True,
        verbose_name='Ricevi notifiche push e Telegram',
    )
    telegram_chat_id = models.CharField(max_length=64, blank=True, verbose_name='Chat Telegram collegata')

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
    tabauno_verifiche = models.JSONField(null=True, blank=True, verbose_name='Verifiche TabaUno')
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
    EXTRACT_JOB_CHOICES = [
        ('', 'Non avviata'),
        ('queued', 'In coda'),
        ('processing', 'In elaborazione'),
        ('ready', 'Pronta'),
        ('error', 'Errore'),
    ]
    extract_job_status = models.CharField(
        max_length=20,
        choices=EXTRACT_JOB_CHOICES,
        blank=True,
        default='',
        verbose_name="Stato job estrazione IA",
    )
    extract_error = models.TextField(blank=True, default='', verbose_name="Errore estrazione IA")
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


class Cliente(models.Model):
    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, related_name='clienti', verbose_name='Azienda',
    )
    ragione_sociale = models.CharField(max_length=255, verbose_name='Ragione sociale')
    indirizzo = models.TextField(blank=True, verbose_name='Indirizzo')
    cf_piva = models.CharField(max_length=32, blank=True, verbose_name='CF/PIVA')
    email = models.EmailField(blank=True, verbose_name='Email')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Cliente'
        verbose_name_plural = 'Clienti'
        ordering = ['ragione_sociale', 'id']

    def __str__(self):
        return self.ragione_sociale


class ValoreBollato(models.Model):
    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, related_name='valori_bollati', verbose_name='Azienda',
    )
    descrizione = models.CharField(max_length=255, verbose_name='Descrizione')
    importo = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='Importo')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Valore bollato'
        verbose_name_plural = 'Valori bollati'
        ordering = ['descrizione', 'id']

    def __str__(self):
        return self.descrizione


class Ricevuta(models.Model):
    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, related_name='ricevute', verbose_name='Azienda',
    )
    cliente = models.ForeignKey(
        Cliente, on_delete=models.PROTECT, related_name='ricevute', verbose_name='Cliente',
    )
    date = models.DateField(verbose_name='Data ricevuta')
    operator = models.CharField(max_length=100, verbose_name='Operatore')
    note = models.TextField(blank=True, verbose_name='Note')
    numero_progressivo = models.PositiveIntegerField(default=1, verbose_name='Numero progressivo')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Ricevuta'
        verbose_name_plural = 'Ricevute'
        ordering = ['-date', '-created_at']

    def __str__(self):
        return f'Ricevuta {self.date} — {self.cliente.ragione_sociale}'


class RicevutaRiga(models.Model):
    TIPO_VALORE_BOLLATO = 'valore_bollato'
    TIPO_CONTRIBUTO_UNIFICATO = 'contributo_unificato'
    TIPO_CHOICES = [
        (TIPO_VALORE_BOLLATO, 'Valori bollati'),
        (TIPO_CONTRIBUTO_UNIFICATO, 'Contributo unificato'),
    ]

    ricevuta = models.ForeignKey(
        Ricevuta, on_delete=models.CASCADE, related_name='righe', verbose_name='Ricevuta',
    )
    tipo = models.CharField(max_length=32, choices=TIPO_CHOICES, verbose_name='Tipo articolo')
    descrizione = models.CharField(max_length=255, verbose_name='Descrizione')
    importo_unitario = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Importo unitario')
    quantita = models.PositiveIntegerField(default=1, verbose_name='Quantità')
    valore_bollato = models.ForeignKey(
        ValoreBollato,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='righe_ricevuta',
        verbose_name='Voce catalogo',
    )

    class Meta:
        verbose_name = 'Riga ricevuta'
        verbose_name_plural = 'Righe ricevuta'
        ordering = ['id']

    @property
    def importo_totale(self):
        return self.importo_unitario * self.quantita

    def __str__(self):
        return f'{self.descrizione} x{self.quantita}'


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


class TabaUnoAgent(models.Model):
    company = models.OneToOneField(Company, on_delete=models.CASCADE, related_name='tabauno_agent')
    token_hash = models.CharField(max_length=64, blank=True, default='')
    last_seen = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Agente TabaUno'
        verbose_name_plural = 'Agenti TabaUno'

    def __str__(self):
        return f'Agente {self.company}'


class TabaUnoRequest(models.Model):
    PENDING = 'pending'
    PROCESSING = 'processing'
    DONE = 'done'
    ERROR = 'error'
    EXPIRED = 'expired'
    STATUS_CHOICES = [
        (PENDING, 'In coda'),
        (PROCESSING, 'In lettura'),
        (DONE, 'Pronta'),
        (ERROR, 'Errore'),
        (EXPIRED, 'Scaduta'),
    ]
    TIPO_CHIUSURA = 'chiusura'
    TIPO_PREORDINE_GRATTA = 'preordine_gratta'
    TIPO_PREORDINE_TABACCHI = 'preordine_tabacchi'
    TIPO_DEPOSITA_ORDINE_LOGISTA = 'deposita_ordine_logista'
    TIPO_PARZIALI_CASSA = 'parziali_cassa'
    TIPO_CHOICES = [
        (TIPO_CHIUSURA, 'Chiusura'),
        (TIPO_PREORDINE_GRATTA, 'Preordine gratta'),
        (TIPO_PREORDINE_TABACCHI, 'Preordine tabacchi'),
        (TIPO_DEPOSITA_ORDINE_LOGISTA, 'Deposita Ordine Logista'),
        (TIPO_PARZIALI_CASSA, 'Parziali cassa'),
    ]

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='tabauno_requests')
    date = models.DateField()
    gratta = models.CharField(max_length=1, default='B')
    tipo = models.CharField(max_length=32, choices=TIPO_CHOICES, default=TIPO_CHIUSURA)
    parametri = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=PENDING)
    requested_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='tabauno_requests')
    payload = models.JSONField(null=True, blank=True)
    error = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    picked_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Richiesta TabaUno'
        verbose_name_plural = 'Richieste TabaUno'
        ordering = ['created_at', 'id']

    def __str__(self):
        return f'{self.company} {self.date} {self.tipo} {self.status}'


class GrattaPreordine(models.Model):
    BOZZA = 'bozza'
    INVIATO_N8N = 'inviato_n8n'
    CARRELLO_PRONTO = 'carrello_pronto'
    CONFERMATO = 'confermato'
    INVIATO_PORTALE = 'inviato_portale'
    ANNULLATO = 'annullato'
    ERRORE = 'errore'
    STATO_CHOICES = [
        (BOZZA, 'Bozza'),
        (INVIATO_N8N, 'Inviato al bot'),
        (CARRELLO_PRONTO, 'Carrello pronto'),
        (CONFERMATO, 'Confermato'),
        (INVIATO_PORTALE, 'Inviato al portale'),
        (ANNULLATO, 'Annullato'),
        (ERRORE, 'Errore'),
    ]

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='gratta_preordini')
    creato_da = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='gratta_preordini')
    creato_il = models.DateTimeField(auto_now_add=True)
    request = models.ForeignKey(TabaUnoRequest, on_delete=models.PROTECT, related_name='preordini_gratta')
    data_consegna = models.DateField()
    giorni_copertura = models.PositiveSmallIntegerField(default=7)
    stato = models.CharField(max_length=32, choices=STATO_CHOICES, default=BOZZA)
    totale = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    messaggio_stato = models.TextField(blank=True, default='')
    payload_inviato = models.JSONField(null=True, blank=True)
    callback_token_hash = models.CharField(max_length=64, blank=True, default='')
    aggiornato_il = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Preordine gratta'
        verbose_name_plural = 'Preordini gratta'
        ordering = ['-creato_il', '-id']

    def __str__(self):
        return f'Preordine gratta {self.id} {self.stato}'


class GrattaPreordineRiga(models.Model):
    preordine = models.ForeignKey(GrattaPreordine, on_delete=models.CASCADE, related_name='righe')
    id_articolo = models.CharField(max_length=80)
    codice = models.CharField(max_length=32)
    descrizione = models.CharField(max_length=200, blank=True, default='')
    prezzo = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    biglietti_pacco = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    valore_pacco = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    giacenza = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    media = models.DecimalField(max_digits=12, decimal_places=4, default=0)
    giorni_esauriti = models.PositiveSmallIntegerField(default=0)
    settimane = models.JSONField(default=list, blank=True)
    pacchi_proposti = models.PositiveIntegerField(default=0)
    pacchi = models.PositiveIntegerField(default=0)
    corretto_a_mano = models.BooleanField(default=False)
    importo = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    escluso = models.BooleanField(default=False)

    class Meta:
        verbose_name = 'Riga preordine gratta'
        verbose_name_plural = 'Righe preordine gratta'
        ordering = ['codice', 'id']

    def __str__(self):
        return f'{self.codice} x{self.pacchi}'


class TabacchiPreordine(models.Model):
    BOZZA = 'bozza'
    ESPORTATO = 'esportato'
    ANNULLATO = 'annullato'
    STATO_CHOICES = [
        (BOZZA, 'Bozza'),
        (ESPORTATO, 'Esportato'),
        (ANNULLATO, 'Annullato'),
    ]

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='tabacchi_preordini')
    creato_da = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='tabacchi_preordini')
    creato_il = models.DateTimeField(auto_now_add=True)
    request = models.ForeignKey(TabaUnoRequest, on_delete=models.PROTECT, related_name='preordini_tabacchi')
    data_consegna = models.DateField()
    giorni_copertura = models.PositiveSmallIntegerField(default=7)
    scorta_pct = models.PositiveSmallIntegerField(default=200)
    stato = models.CharField(max_length=32, choices=STATO_CHOICES, default=BOZZA)
    totale = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    kg = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    aggiornato_il = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Preordine tabacchi'
        verbose_name_plural = 'Preordini tabacchi'
        ordering = ['-creato_il', '-id']

    def __str__(self):
        return f'Preordine tabacchi {self.id} {self.stato}'


class TabacchiPreordineRiga(models.Model):
    preordine = models.ForeignKey(TabacchiPreordine, on_delete=models.CASCADE, related_name='righe')
    aams = models.CharField(max_length=32)
    descrizione = models.CharField(max_length=200, blank=True, default='')
    famiglia = models.CharField(max_length=64, blank=True, default='')
    prezzo = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    pacchetti_per_unita = models.PositiveIntegerField(default=0)
    kg_per_unita = models.DecimalField(max_digits=10, decimal_places=3, default=0)
    giacenza = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    media = models.DecimalField(max_digits=12, decimal_places=4, default=0)
    data_fine = models.DateField(null=True, blank=True)
    unita_proposte = models.PositiveIntegerField(default=0)
    unita = models.PositiveIntegerField(default=0)
    corretto_a_mano = models.BooleanField(default=False)
    importo = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    class Meta:
        verbose_name = 'Riga preordine tabacchi'
        verbose_name_plural = 'Righe preordine tabacchi'
        ordering = ['aams', 'id']

    def __str__(self):
        return f'{self.aams} x{self.unita}'


class LogistaInvioJob(models.Model):
    """Caricamento nella proposta WebT e invio definitivo tramite il servizio locale «logista»."""
    IN_CORSO_CARICAMENTO = 'in_corso_caricamento'
    IN_CORSO_INVIO = 'in_corso_invio'
    ATTESA_CONFERMA = 'attesa_conferma'
    INVIATO = 'inviato'
    NON_INVIATO = 'non_inviato'
    INCERTO = 'incerto'
    ERRORE = 'errore'
    STATO_CHOICES = [
        (IN_CORSO_CARICAMENTO, 'Caricamento righe'),
        (IN_CORSO_INVIO, 'Invio ordine'),
        (ATTESA_CONFERMA, 'Attesa conferma'),
        (INVIATO, 'Inviato'),
        (NON_INVIATO, 'Non inviato'),
        (INCERTO, 'Esito incerto'),
        (ERRORE, 'Errore'),
    ]
    STATI_IN_CORSO = (IN_CORSO_CARICAMENTO, IN_CORSO_INVIO)
    STATI_FINALI = (ATTESA_CONFERMA, INVIATO, NON_INVIATO, INCERTO, ERRORE)
    ORIGINE_PAGINA = 'pagina'
    ORIGINE_TELEGRAM = 'telegram'
    ORIGINE_CHOICES = [
        (ORIGINE_PAGINA, 'Pagina'),
        (ORIGINE_TELEGRAM, 'Telegram'),
    ]

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='logista_jobs')
    preordine = models.ForeignKey(
        TabacchiPreordine, null=True, blank=True, on_delete=models.SET_NULL, related_name='logista_jobs',
    )
    creato_da = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='logista_jobs')
    stato = models.CharField(max_length=24, choices=STATO_CHOICES, default=IN_CORSO_CARICAMENTO)
    fase = models.CharField(max_length=32, blank=True, default='')
    codice_ordine = models.CharField(max_length=64, blank=True, default='')
    data_consegna_logista = models.CharField(max_length=16, blank=True, default='')
    foto_invio_path = models.CharField(max_length=255, blank=True, default='')
    notifica_esito = models.JSONField(null=True, blank=True)
    origine = models.CharField(max_length=16, choices=ORIGINE_CHOICES, default=ORIGINE_PAGINA)
    svuota = models.BooleanField(default=False)
    creato_il = models.DateTimeField(auto_now_add=True)
    aggiornato_il = models.DateTimeField(auto_now=True)
    righe_inviate = models.PositiveIntegerField(default=0)
    righe_presenti = models.PositiveIntegerField(null=True, blank=True)
    risultato = models.JSONField(null=True, blank=True)
    foto_path = models.CharField(max_length=255, blank=True, default='')
    errore = models.TextField(blank=True, default='')

    class Meta:
        verbose_name = 'Invio proposta Logista'
        verbose_name_plural = 'Invii proposta Logista'
        ordering = ['-creato_il', '-id']

    def __str__(self):
        return f'Logista job {self.id} {self.stato}'
