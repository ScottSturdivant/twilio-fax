import os
import twilio
from pathlib import Path
from wtforms import ValidationError
from wtforms.fields import StringField
from twilio.rest import Client
from flask import Flask, request, url_for, send_from_directory, redirect, render_template, flash
from flask_bootstrap import Bootstrap
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileRequired, FileAllowed
from wtforms.validators import DataRequired
from werkzeug import secure_filename

app = Flask(__name__)
Bootstrap(app)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY') or os.urandom(32)
app.config['UPLOAD_FOLDER'] = '/tmp/'
app.config['ALLOWED_EXTENSIONS'] = {'pdf',}
app.config['TWILIO_ACCOUNT_SID'] = os.getenv('TWILIO_ACCOUNT_SID')
app.config['TWILIO_ACCOUNT_TOKEN'] = os.getenv('TWILIO_ACCOUNT_TOKEN')
app.config['FAX_FROM_NUMBER'] = os.getenv('FAX_FROM_NUMBER')
app.config['SMS_TO_NUMBER'] = os.getenv('SMS_TO_NUMBER')

app.client = Client(
    app.config['TWILIO_ACCOUNT_SID'],
    app.config['TWILIO_ACCOUNT_TOKEN']
)

class FaxSubmitForm(FlaskForm):
    to = StringField(validators=[DataRequired(),])
    fax = FileField(validators=[FileRequired(), FileAllowed(app.config['ALLOWED_EXTENSIONS'], 'PDFs only!')])

    def validate_to(form, field):
        try:
            field.data = app.client.lookups.phone_numbers(field.data).fetch().phone_number
        except twilio.base.exceptions.TwilioRestException:
            raise ValidationError('Invalid phone number.')

@app.route('/', methods=['GET', 'POST'])
def upload():
    form = FaxSubmitForm()
    if form.validate_on_submit():
        f = form.fax.data
        filename = secure_filename(f.filename)
        f.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

        kwargs = {
            'from_': app.config['FAX_FROM_NUMBER'],
            'to': form.to.data,
            'media_url': url_for('download_file', filename=filename, _external=True),
            'status_callback': url_for('callback', _external=True),
        }
        app.client.fax.faxes.create(**kwargs)
        flash('The fax has been submitted!')
        return redirect(url_for('upload'))
    return render_template('fax.html', form=form)

@app.route('/uploads/<path:filename>')
def download_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/callback', methods=['POST'])
def callback():
    status = request.form

    # Delete the file from the file system
    filename = Path(status['OriginalMediaUrl']).parts[-1]
    uploaded_file = Path(app.config['UPLOAD_FOLDER']) / filename
    if uploaded_file.is_file():
        uploaded_file.unlink()

    # send status SMS
    to = status['To']
    if status['Status'] == 'delivered':
        body = f'Your fax to {to} has been sent!'
    else:
        body = f'Your fax to {to} has failed. :-('
    app.client.messages.create(
        body=body,
        from_=app.config['FAX_FROM_NUMBER'],
        to=app.config['SMS_TO_NUMBER'],
    )

    return ''  # Twilio appreciates a 200 response.
