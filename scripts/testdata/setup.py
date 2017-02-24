from squad.core.models import Group, Project

team1 = Group.objects.create(slug='team1')
team2 = Group.objects.create(slug='team2')
team3 = Group.objects.create(slug='team3')

project1 = team1.projects.create(slug='project1')
project2 = team2.projects.create(slug='project2')
project3 = team3.projects.create(slug='project3')

token1 = project1.tokens.create(key='key1', description='Key 1')
token2 = project2.tokens.create(key='key2', description='Key 2')
token3 = project3.tokens.create(key='key3', description='Key 3')
