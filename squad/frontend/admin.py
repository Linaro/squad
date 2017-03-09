from django.contrib import admin
from django.conf import settings


admin_site_name = '%s administration' % settings.SITE_NAME
admin.site.site_title = admin_site_name
admin.site.site_header = admin_site_name
