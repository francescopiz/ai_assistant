import smtplib
from email.message import EmailMessage
import os
from dotenv import load_dotenv


load_dotenv()

EMAIL_MITTENTE = os.environ.get("EMAIL_USER")
PASSWORD_APP = os.environ.get("EMAIL_PASS")

msg = EmailMessage()
msg['Subject'] = 'Email Automatica'
msg['To'] = 'francy.pizzuto@gmail.com'
msg.set_content('Ciao! Questa è un email automatica inviata con Python.')

with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
    smtp.login(EMAIL_MITTENTE, PASSWORD_APP)
    smtp.send_message(msg)

#per leggere
import imaplib
import email
# Connessione al server IMAP
mail = imaplib.IMAP4_SSL('imap.gmail.com')
mail.login(EMAIL_MITTENTE, PASSWORD_APP)
mail.select('inbox')
# Cerca tutte le email non lette
status, data = mail.search(None, 'UNSEEN')

for num in data[0].split():
    status, msg_data = mail.fetch(num, '(RFC822)')
    for response_part in msg_data:
        if isinstance(response_part, tuple):
            msg = email.message_from_bytes(response_part[1])
            print(f"Da: {msg['from']}")
            print(f"Oggetto: {msg['subject']}")