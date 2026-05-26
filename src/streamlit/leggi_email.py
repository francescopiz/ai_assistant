import os
from dotenv import load_dotenv
import imaplib
import email

load_dotenv()

EMAIL_MITTENTE = os.environ.get("EMAIL_USER")
PASSWORD_APP = os.environ.get("EMAIL_PASS")

mail = imaplib.IMAP4_SSL('imap.gmail.com')
mail.login(EMAIL_MITTENTE, PASSWORD_APP)
mail.select('inbox')
status, data = mail.search(None, 'UNSEEN')

for num in data[0].split():
    status, msg_data = mail.fetch(num, '(RFC822)')
    for response_part in msg_data:
        if isinstance(response_part, tuple):
            msg = email.message_from_bytes(response_part[1])
            print(f"Da: {msg['from']}")
            print(f"Oggetto: {msg['subject']}")
