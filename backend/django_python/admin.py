from django.contrib import admin
from .models import RepositoryScan, UserInputModel

# Register your models here.
admin.site.register(RepositoryScan)
admin.site.register(UserInputModel)
