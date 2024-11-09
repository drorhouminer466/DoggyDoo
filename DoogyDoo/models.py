from django.db import models
from pymongo import MongoClient
from db_connection import db


Employees_collections = db['Employees']
Bag_Stations_collections=db['Bag_Stations']
Reports_collections=db['Reports']
Reports_Handling_collections=db['Reports_Handling']
Local_Authority_collections=db['Local_Authority']