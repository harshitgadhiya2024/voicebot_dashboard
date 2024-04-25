"""
Maintain mongodb connection and all operation handling in here
"""

from pymongo import MongoClient
from init import enviroment

def mongo_connect(app):
    """
    Connection of mongodb

    :param app: app-name
    :return: mongodb client object
    """
    try:
        get_mongourl = enviroment[app.config["enviroment"]]["Mongourl"]
        client = MongoClient(get_mongourl)
        return client

    except Exception as e:
        app.logger.error(f"Error when connecting mongo: {e}")


def data_added(app, db, coll_name, new_dict):

    """
    Add data from any collection

    :param app: app-name
    :param db: database-name
    :param coll_name: collection-name
    :param new_dict: data dict
    :return: status
    """
    try:
        coll = db[coll_name]
        coll.insert_one(new_dict)
        return "add_data"

    except Exception as e:
        app.logger.error(f"Error when save data in database: {e}")

# get all data from my table from database
def find_all_data(app, db, coll_name):
    """
    find all data in database collection

    :param app: app-name
    :param db: database-name
    :param coll_name: collection-name
    :return: response cursor_object
    """
    try:
        coll = db[coll_name]
        res = coll.find({})
        return res

    except Exception as e:
        app.logger.error(f"Error when fetch all data in database: {e}")

# get only specific data from my database
def find_spec_data(app, db, coll_name, di):
    """
    find specific data in database collection with condition based

    :param app: app-name
    :param db: database-name
    :param coll_name: collection-name
    :param di: condition-dict
    :return: response cursor_object
    """
    try:
        coll = db[coll_name]
        res = coll.find(di)
        return res

    except Exception as e:
        app.logger.error(f"Error when fetch specific data in database: {e}")

def delete_data(app, db, coll_name, di):
    """
    Delete data from collection with condition

    :param app: app-name
    :param db: database-name
    :param coll_name: collection-name
    :param di: condition-dict
    :return: response cursor_object
    """
    try:
        coll = db[coll_name]
        res = coll.delete_one(di)
        return res

    except Exception as e:
        app.logger.error(f"Error when delete data in database: {e}")

def update_mongo_data(app, db, coll_name, condition_dict, update_data):
    """
    update data from collection

    :param app: app-name
    :param db: database-name
    :param coll_name: collection-name
    :param prev_data: condition-dict
    :param update_data: updated data dict
    :return: status
    """
    try:
        coll = db[coll_name]
        coll.update_one(condition_dict, {"$set": update_data})
        return "updated"

    except Exception as e:
        app.logger.error(f"Error when update data in database: {e}")
