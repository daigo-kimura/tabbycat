# -*- coding: utf-8 -*-
# Generated by Django 1.9.7 on 2016-06-21 11:27
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    operations = [
        migrations.CreateModel(
            name='Division',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=50, verbose_name='Name or suffix')),
                ('seq', models.IntegerField(blank=True, help_text='The order in which divisions are displayed', null=True)),
                ('time_slot', models.TimeField(blank=True, null=True)),
                ('tournament', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='tournaments.Tournament')),
                ('venue_group', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='venues.VenueGroup')),
            ],
            options={
                'ordering': ['tournament', 'seq'],
            },
        ),
        migrations.AlterUniqueTogether(
            name='division',
            unique_together=set([('tournament', 'name')]),
        ),
        migrations.AlterIndexTogether(
            name='division',
            index_together=set([('tournament', 'seq')]),
        ),
    ]