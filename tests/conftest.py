import os
import tempfile

# Separate test DB; never write fixtures into the user's production database.
os.environ['SAITAN_DATA_DIR'] = tempfile.mkdtemp(prefix='saitan-test-')
os.environ['SAITAN_API_KEY'] = ''
os.environ['ANONYMIZED_TELEMETRY'] = 'false'
