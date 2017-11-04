# -*- coding: utf-8 -*-
# Generated by Django 1.11.7 on 2017-11-04 18:05
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('adjfeedback', '0012_auto_20171005_1652'),
    ]

    operations = [
        migrations.AlterField(
            model_name='adjudicatorfeedbackquestion',
            name='name',
            field=models.CharField(help_text='A short name for the question, e.g., "Agree with decision"', max_length=30, verbose_name='name'),
        ),
    ]
