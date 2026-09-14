pip install --upgrade pip
# install Dependencies
pip install --upgrade pip setuptools wheel && pip install -r requirements.txt
# run Migrations
python manage.py migrate

python manage.py collectstatic --noinput
