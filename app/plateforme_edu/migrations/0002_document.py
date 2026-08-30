from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('plateforme_edu', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Document',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('doc_id', models.CharField(max_length=64, unique=True)),
                ('titre', models.CharField(max_length=200)),
                ('matiere', models.CharField(
                    choices=[
                        ('maths_pc_svt', 'Maths / Physique-Chimie / SVT'),
                        ('generation_resume', 'Génération / Résumé'),
                        ('histoire_geo', 'Histoire / Géographie'),
                    ],
                    default='generation_resume',
                    max_length=30,
                )),
                ('date_ajout', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'ordering': ['-date_ajout'],
            },
        ),
    ]
