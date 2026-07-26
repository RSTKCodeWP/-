import os, sys, site

site.addsitedir('/home/winkwebdev/.virtualenvs/comm/lib/python2.7/site-packages')

os.environ['DJANGO_SETTINGS_MODULE'] = 'comm.settings'

activate_this = os.path.expanduser("~/.virtualenvs/comm/bin/activate_this.py")
execfile(activate_this, dict(__file__=activate_this))

# Calculate the path based on the location of the WSGI script
project = '/home/winkwebdev/webapps/comm_gamers_prod/comm/'
workspace = os.path.dirname(project)
sys.path.append(workspace)

sys.path = ['/home/winkwebdev/webapps/comm_gamers_prod/comm', '/home/winkwebdev/webapps/cmom_gamers_prod/comm/apps', '/home/winkwebdev/webapps/comm_gamers_prod'] + sys.path

from django.core.handlers.wsgi import WSGIHandler
application = WSGIHandler()
