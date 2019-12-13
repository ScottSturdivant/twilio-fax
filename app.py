import os
import requests
import smtplib
import twilio
from email.message import EmailMessage
from twilio.rest import Client
from flask import Flask, request, url_for, Response

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY') or os.urandom(32)
app.config['TWILIO_ACCOUNT_SID'] = os.getenv('TWILIO_ACCOUNT_SID')
app.config['TWILIO_ACCOUNT_TOKEN'] = os.getenv('TWILIO_ACCOUNT_TOKEN')
app.config['EMAIL_HOST'] = os.getenv('EMAIL_HOST')
app.config['EMAIL_PORT'] = os.getenv('EMAIL_PORT')
app.config['EMAIL_FROM'] = os.getenv('EMAIL_FROM')
app.config['EMAIL_TO'] = os.getenv('EMAIL_TO') or app.config['EMAIL_FROM']
app.config['EMAIL_PASSWORD'] = os.getenv('EMAIL_PASSWORD')

app.client = Client(
    app.config['TWILIO_ACCOUNT_SID'],
    app.config['TWILIO_ACCOUNT_TOKEN']
)

@app.route('/fax/sent', methods=['POST'])
def fax_sent():
    accept_url = url_for('fax_received')
    twiml = f'<Response><Receive action="{accept_url}"/></Response>'
    return Response(twiml, mimetype='text/xml')


@app.route('/fax/received', methods=['POST'])
def fax_received():

    # Fetch the fax from Twilio's server
    fax = requests.get(request.form.get('MediaUrl'))

    # Send the received fax file as an email attachment
    msg = EmailMessage()
    msg['Subject'] = 'Fax from {} received.'.format(request.form.get('From'))
    msg['From'] = app.config['EMAIL_FROM']
    msg['To'] = app.config['EMAIL_TO']
    msg.add_attachment(fax.content, maintype='application', subtype='pdf')

    with smtplib.SMTP_SSL(app.config['EMAIL_HOST'], app.config['EMAIL_PORT']) as server:
        server.login(app.config['EMAIL_FROM'], app.config['EMAIL_PASSWORD'])
        server.send_message(msg)

    # Finally, we can cleanup and remove the fax from Twilio's servers.
    app.client.fax.faxes(request.form.get('FaxSid')).delete()

    return ''  # Twilio appreciates a 200 response.
