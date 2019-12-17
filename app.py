import os
import requests
import twilio
from twilio.rest import Client
from twilio.request_validator import RequestValidator
from flask import Flask, request, url_for, Response, abort
from flask_mail import Mail, Message
from functools import wraps


app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY') or os.urandom(32)
app.config['TWILIO_ACCOUNT_SID'] = os.getenv('TWILIO_ACCOUNT_SID')
app.config['TWILIO_ACCOUNT_TOKEN'] = os.getenv('TWILIO_ACCOUNT_TOKEN')
app.config['MAIL_SERVER'] = os.getenv('MAIL_SERVER')
app.config['MAIL_PORT'] = os.getenv('MAIL_PORT')
app.config['MAIL_USE_TLS'] = os.getenv('MAIL_USE_TLS', False)
app.config['MAIL_USE_SSL'] = os.getenv('MAIL_USE_SSL', False)
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
app.config['MAIL_TO'] = os.getenv('MAIL_TO') or app.config['MAIL_USERNAME']
app.config['MAIL_FROM'] = os.getenv('MAIL_FROM') or app.config['MAIL_USERNAME']
mail = Mail(app)

app.client = Client(
    app.config['TWILIO_ACCOUNT_SID'],
    app.config['TWILIO_ACCOUNT_TOKEN']
)

def twilio_originating(f):
    """This decorator ensures that we only accept requests from Twilio."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        validator = RequestValidator(app.config['TWILIO_ACCOUNT_TOKEN'])
        if not validator.validate(request.url, request.form, request.headers.get('X-Twilio-Signature', '')):
            abort(401)
        return f(*args, **kwargs)
    return decorated_function

@app.route('/fax/incoming', methods=['POST'])
@twilio_originating
def fax_incoming():
    accept_url = url_for('fax_received', _external=True)
    twiml = '<Response><Receive action="{}"/></Response>'.format(accept_url)
    return Response(twiml, mimetype='text/xml')


@app.route('/fax/received', methods=['POST'])
@twilio_originating
def fax_received():

    # Fetch the fax from Twilio's server
    fax = requests.get(request.form.get('MediaUrl'))

    # Send the received fax file as an email attachment
    msg = Message(
        'Fax from {} received.'.format(request.form.get('From')),
        sender=app.config['MAIL_FROM'],
        recipients=[app.config['MAIL_TO']]
    )
    msg.attach('fax.pdf', 'application/pdf', fax.content)
    mail.send(msg)

    # Finally, we can cleanup and remove the fax from Twilio's servers.
    app.client.fax.faxes(request.form.get('FaxSid')).delete()

    return ''  # Twilio appreciates a 200 response.
