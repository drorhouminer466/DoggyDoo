from django.contrib.sites import requests
from django.shortcuts import render, redirect
from .models import Employees_collections, Bag_Stations_collections, Reports_collections, Reports_Handling_collections,Local_Authority_collections
from django.http import HttpResponse, JsonResponse
import math
from bson import ObjectId
from .report_form import ReportForm
from pymongo import MongoClient
from bson.errors import InvalidId
from datetime import datetime,timedelta
import json
from geopy.distance import geodesic
from django.core.files.storage import default_storage

client = MongoClient('mongodb://localhost:27017')
db = client['Doggy_Doo']



# Create your views here.
def index(request):

    return HttpResponse("<h1> App is running..</h1>")


def login(request, station_id):
    return render(request, "Login.html", {'station_id': station_id})

def managerLogin(request):
    return render(request, "LoginManager.html")

def check_user_manager(request):
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")
        employee_type = request.POST.get("Employee_Type")
        #station_id = request.POST.get("station_id")
        # Query MongoDB to find the user with given username and password
        user = Employees_collections.find_one({'User_Name': username, 'Password': password})

        if user:
            if user["Employee_Type"] == "employee":
                return redirect('employeeAlert')

            else:
                return redirect('dashboard')
        else:
            error_message = 'Invalid username or password.'
            return render(request, 'LoginManager.html', {'error': error_message})
    else:
        return render(request, 'LoginManager.html')  # Render the login form initially


def employeealert(request):
    Radius = 150
    EmptyStaions = 70
    lastRestock = 48

    if request.method == "POST":
        form_type = request.POST.get('form_type')
        if form_type == "potential":
            Radius = int(request.POST.get("radius", 150))  # Use POST value or default to 150
            EmptyStaions = int(request.POST.get("emptyStations", 70))  # Use POST value or default to 70
            lastRestock = int(request.POST.get("lastRestock", 48))  # Use POST value or default to 48
            update_station = update_neighbors_in_mongodb(Radius)
            # Handle the potential form submission

    else:
        update_station = update_neighbors_in_mongodb(150)

    # Fetch open reports
    open_reports = list(Reports_collections.find({'Close_Date': {'$exists': False}}))

    # Fetch last report handling and ensure station_id is included
    last_report_handle = list(last_report_handle_date(EmptyStaions, lastRestock))

    # Add the station_id to each item in last_report_handle (assuming station_id is available)
    for report in last_report_handle:
        station_id = report.get('station_id')
        if station_id:
            report['station_id'] = station_id
        else:
            report['station_id'] = 'Station ID not available'

    # Fetch station details
    station_ids = [report['station_id'] for report in open_reports]
    stations = list(Bag_Stations_collections.find({'_id': {'$in': station_ids}}))

    # Create dictionaries for mapping station details
    station_id_to_address = {station['_id']: station['address'] for station in stations}
    station_id_to_area = {station['_id']: station['Area'] for station in stations}
    station_id_to_coordinates = {station['_id']: station['location_coordinates'] for station in stations}

    # Update the open_reports with the station details
    for report in open_reports:
        report['address'] = station_id_to_address.get(report['station_id'], 'Address not found')
        report['area'] = station_id_to_area.get(report['station_id'], 'Area not found')
        report['coordinates'] = station_id_to_coordinates.get(report['station_id'], 'coordinates not found')

        if report.get('Report_Type') == 'Area':
            report['report_type_label'] = 'אזור מלוכלך'
        else:
            report['report_type_label'] = 'עמדה ריקה'

    # Sort open reports by Open_Date
    open_reports.sort(key=lambda x: x.get('Open_Date', None))

    local_authority = local_authority_info()

    # Render the template with the context data
    return render(request, 'employeeAlert.html', {
        'open_reports': open_reports,
        'last_handling': last_report_handle,
        'radius': Radius,
        'EmptyStaions': EmptyStaions,
        'lastRestock': lastRestock,
        'local_authority': local_authority
    })


def route_map(request):

    if request.method == "POST":
        selected_stations_ids = request.POST.getlist('selected_stations')
        print(selected_stations_ids)

        if not selected_stations_ids:
            return redirect('employeeAlert')  # Redirect back if no stations are selected

        # Convert IDs to ObjectId if needed
        try:
            selected_stations_ids = [ObjectId(id) for id in selected_stations_ids]
        except Exception as e:
            print(f"Error converting IDs: {e}")
            return redirect('employeeAlert')

        # Fetch selected stations from the database
        selected_stations = list(Bag_Stations_collections.find({'_id': {'$in': selected_stations_ids}}))
        print(selected_stations)

        # Extract coordinates for the selected stations
        stations_coords = [
            (station['_id'], (station['location_coordinates']['lat'], station['location_coordinates']['lng']))
            for station in selected_stations
        ]
        print(stations_coords)

        # Define the starting coordinates
        start_coords = (32.0837785153373, 34.780481341677955)

        # Simple greedy algorithm to determine the route
        if stations_coords:
            route = greedy_route(stations_coords, start_coords)
        else:
            route = []

        last_station_coords = route[-1][1] if route else None

        return render(request, 'route_map.html', {'route': route, 'last_station_coords': last_station_coords})

    return redirect('employeeAlert')

def greedy_route(stations, start_coords):
    if not stations:
        return []

    # Start from the specified coordinates
    start_station = ("start", start_coords)
    route = [start_station]

    remaining_stations = stations.copy()

    while remaining_stations:
        last_station = route[-1]
        next_station = min(
            remaining_stations,
            key=lambda station: geodesic(last_station[1], station[1]).meters
        )
        route.append(next_station)
        remaining_stations.remove(next_station)

    # Return to the starting coordinates at the end of the route
    route.append(start_station)

    return route

def last_report_handle_date(EmptyStaions, lastRestock):
    # Fetch all reports handling data
    reports = list(Reports_Handling_collections.find())
    latest_handling_dates = {}

    for report in reports:
        station_id = report['Station_id']
        handling_date = report.get('Handling_Date')

        if isinstance(handling_date, str):
            handling_date = datetime.strptime(handling_date, '%Y-%m-%d')  # Adjust the format as needed

        if station_id in latest_handling_dates:
            if handling_date > latest_handling_dates[station_id]['last_date']:
                latest_handling_dates[station_id]['last_date'] = handling_date
        else:
            latest_handling_dates[station_id] = {
                '_id': station_id,
                'last_date': handling_date
            }

    # Get station IDs and fetch station details
    station_ids = list(latest_handling_dates.keys())
    stations = list(Bag_Stations_collections.find({'_id': {'$in': station_ids}, 'Bags_Status': {'$ne': 'empty'}}))

    # Add station details to the result
    latest_handling_dates_list = []
    for station in stations:
        station_id = station['_id']
        neighbors = station.get('neighbors', [])

        # Extract station_id from each neighbor object
        neighbor_station_ids = [neighbor['station_id'] for neighbor in neighbors if 'station_id' in neighbor]

        # Fetch neighbors' details using their station_id
        neighbors_details = list(Bag_Stations_collections.find({'_id': {'$in': neighbor_station_ids}}))

        # Fetch the latest handling date for each neighbor
        for neighbor in neighbors_details:
            neighbor_station_id = neighbor['_id']
            neighbor['last_report_handle_date'] = latest_handling_dates.get(neighbor_station_id, {}).get('last_date')

        # Extract addresses, Bags_Status, and last handling date from neighbors
        neighbor_info = [
            {
                'station_id': neighbor['_id'],
                'address': neighbor.get('address', 'Unknown'),
                'Bags_Status': neighbor.get('Bags_Status', 'Unknown'),
                'last_report_handle_date': neighbor.get('last_report_handle_date', 'N/A')
            } for neighbor in neighbors_details
        ]

        # Count the number of neighbors with Bags_Status = "empty"
        empty_neighbors_count = sum(1 for neighbor in neighbors_details if neighbor.get('Bags_Status') == 'empty')

        # Total number of neighbors
        total_neighbors_count = len(neighbors_details)

        # Calculate the ratio and convert it to a percentage
        empty_neighbors_ratio = (empty_neighbors_count / total_neighbors_count * 100) if total_neighbors_count > 0 else 0

        # Calculate hours since last handling date
        now = datetime.now()
        last_date = latest_handling_dates[station_id]['last_date']
        hours_since_last = (now - last_date).total_seconds() / 3600

        # Only add stations with empty_neighbors_ratio > EmptyStaions and last handling within lastRestock hours
        if empty_neighbors_ratio > EmptyStaions or hours_since_last > lastRestock:
            latest_handling_dates_list.append({
                'id': station_id,
                'last_date': last_date,
                'neighbors': neighbor_info,
                'Area': station.get('Area', 'Unknown'),
                'Bags_Status': station.get('Bags_Status', 'Unknown'),
                'address': station.get('address', 'Unknown'),
                'empty_neighbors_count': empty_neighbors_count,
                'empty_neighbors_ratio': f"{int(empty_neighbors_ratio)}%"  # Format as percentage with no decimal digits
            })

    return latest_handling_dates_list

def update_delivery_time(deliverytime):
    Local_Authority_collections.update_one(
        {'Local_Authority_name': 'תל אביב'},  # Filter for the document to update
        {"$set": {"Delivery_time": deliverytime}}  # Increment the Delivery_time field
    )

def local_authority_info():
    Local_Authority_info = Local_Authority_collections.find_one({'Local_Authority_name': 'תל אביב'})

    return Local_Authority_info


def manageralert(request):
    Radius = 300
    EmptyStaions = 70
    lastRestock = 48
    cost=100

    if request.method == "POST":
        form_type = request.POST.get('form_type')
        if form_type == "potential":
            Radius = int(request.POST.get("radius", 300))  # Use POST value or default to 150
            EmptyStaions = int(request.POST.get("emptyStations", 70))  # Use POST value or default to 70
            lastRestock = int(request.POST.get("lastRestock", 48))  # Use POST value or default to 48
            update_station = update_neighbors_in_mongodb(Radius)
            # Handle the potential form submission
        elif form_type == "model":
            cost = request.POST.get("cost", "100")  # Default to "100" if cost is not provided
            try:
                cost = int(cost) if cost else 100  # Use 100 if the input is an empty string
            except ValueError:
                cost = 100
            deliverytime = int(request.POST.get("deliverytime", 2))
            update_delivery = update_delivery_time(deliverytime)
            # Handle the model form submission

    else:
        update_station = update_neighbors_in_mongodb(150)
        update_delivery = update_delivery_time(2)
    open_reports = list(Reports_collections.find({'Close_Date': {'$exists': False}}))
    last_report_handle = list(last_report_handle_date(EmptyStaions,lastRestock))
    print(last_report_handle)
    station_ids = [report['station_id'] for report in open_reports]
    stations = list(Bag_Stations_collections.find({'_id': {'$in': station_ids}}))

    station_id_to_address = {station['_id']: station['address'] for station in stations}
    station_id_to_area = {station['_id']: station['Area'] for station in stations}


    for report in open_reports:
        report['address'] = station_id_to_address.get(report['station_id'], 'Address not found')
        report['area'] = station_id_to_area.get(report['station_id'], 'Area not found')


        if report.get('Report_Type') == 'Area':
            report['report_type_label'] = 'אזור מלוכלך'
        else:
            report['report_type_label'] = 'עמדה ריקה'

    open_reports.sort(key=lambda x: x.get('Open_Date', None))
    local_authority=local_authority_info()
    year_demand=count_open_reports_last_3month()*4
    #year_demand=1000
    stock_quantity_make_order=math.ceil((local_authority['Delivery_time']/52)*year_demand)
    quantity_order=round((2*cost*year_demand)**0.5)*100



    return render(request, 'manageralerts.html', {'open_reports': open_reports, 'last_handling': last_report_handle,'radius':Radius,'EmptyStaions':EmptyStaions,
                                                  'lastRestock':lastRestock,'local_authority':local_authority,'year_demand':year_demand,'stock_quantity_make_order':stock_quantity_make_order,'cost':cost,'quantity_order':quantity_order})


def mainwindow(request, station_id):
    try:
        # Try to convert the station_id to an ObjectId
        object_id = ObjectId(station_id)
    except InvalidId:
        # If the station_id is invalid, render the "Missing_station" page
        return render(request, "Missing_station.html")

    current_station = Bag_Stations_collections.find_one({'_id': object_id})

    if current_station:
        current_station['id'] = str(current_station['_id'])  # Add 'id' as a string
        return render(request, "mainwindow.html", {'current_station': current_station})
    else:
        return render(request, "Missing_station.html")

def Report_Handle(request, station_id,employee_id):
    return render(request, "Report_Handle.html", {'station_id': station_id,'employee_id':employee_id})


def get_top_empolyees_with_reports():
    pipeline = [
        {
            '$match': {
                'Employee_id': { '$exists': True }
            }
        },
        {
            '$group': {
                '_id': '$Employee_id',
                'count': {'$sum': 1}
            }
        },
        {
            '$sort': {'count': -1}
        },
        {
            '$limit': 5
        },
        {
            '$lookup': {
                'from': 'Employees',
                'localField': '_id',
                'foreignField': '_id',
                'as': 'employee_details'
            }
        },
        {
            '$unwind': '$employee_details'
        },
        {
            '$project': {
                '_id': 1,
                'count': 1,
                'first_name': '$employee_details.First_Name'
            }

        }
    ]

    result = list(Reports_Handling_collections.aggregate(pipeline))
    print(result)
    return result



def avg_time_between_reports():
    pipeline = [
        {
            '$sort': {'station_id': 1, 'Open_Date': 1}
        },

        {'$match': {'Report_Type': 'Bag'}},

        {
            '$group': {
                '_id': '$station_id',
                'reports': {
                    '$push': {
                        'openDate': '$Open_Date',
                        'closeDate': '$Close_Date'
                    }
                }
            }
        },
        {
            '$project': {
                'reportPairs': {
                    '$map': {
                        'input': {
                            '$range': [
                                1,
                                {'$size': '$reports'}
                            ]
                        },
                        'as': 'index',
                        'in': {
                            'closeDatePrev': {'$arrayElemAt': ['$reports.closeDate', {'$subtract': ['$$index', 1]}]},
                            'openDateNext': {'$arrayElemAt': ['$reports.openDate', '$$index']}
                        }
                    }
                }
            }
        },
        {
            '$project': {
                'avgTimeDiffDays': {
                    '$round': [
                        {
                            '$avg': {
                                '$map': {
                                    'input': '$reportPairs',
                                    'as': 'pair',
                                    'in': {
                                        '$divide': [
                                            {
                                                '$subtract': [
                                                    {'$ifNull': ['$$pair.openDateNext', datetime(1970, 1, 1)]},
                                                    {'$ifNull': ['$$pair.closeDatePrev', datetime(1970, 1, 1)]}
                                                ]
                                            },
                                            1000 * 60 * 60 * 24  # Convert milliseconds to days
                                        ]
                                    }
                                }
                            }
                        },
                        0  # Number of decimal places to round to
                    ]
                }
            }
        },
        {
            '$lookup': {
                'from': 'Bag_Stations',
                'localField': '_id',
                'foreignField': '_id',
                'as': 'station_details'
            }
        },
        {
            '$unwind': '$station_details'
        },
        {
            '$project': {
                'Station_ID': '$_id',
                'avgTimeDiffDays': 1,
                'address': '$station_details.address',
                'area': '$station_details.Area'
            }
        }
    ]

    result = list(Reports_collections.aggregate(pipeline))
    print(result)
    return result





def get_top_stations_with_reports():
    pipeline = [
        {
            '$match': {
                'station_id': { '$exists': True }
            }
        },
        {
            '$group': {
                '_id': '$station_id',
                'count': {'$sum': 1}
            }
        },
        {
            '$sort': {'count': -1}
        },
        {
            '$limit': 5
        },
        {
            '$lookup': {
                'from': 'Bag_Stations',
                'localField': '_id',
                'foreignField': '_id',
                'as': 'station_details'
            }
        },
        {
            '$unwind': '$station_details'
        },
        {
            '$project': {
                '_id': 1,
                'count': 1,
                'address': '$station_details.address'
            }

        }
    ]

    result = list(Reports_collections.aggregate(pipeline))
    return result


def count_closed_report_last_week():
    # Get the current date and calculate the date one week ago
    current_date = datetime.now()
    one_week_ago = current_date - timedelta(days=7)

    # Perform the aggregation query
    pipeline = [
        {
            '$match': {
                'Open_Date': {
                    '$gte': one_week_ago,
                    '$lte': current_date
                },
                'Close_Date': {'$exists': True}  # Only consider reports that have been closed
            }
        },
        {
            '$count': 'closed_reports_last_week'  # Use the correct key name
        }
    ]

    result = list(Reports_collections.aggregate(pipeline))

    # Extract the count from the result
    if result:
        closed_reports_count = result[0]['closed_reports_last_week']
    else:
        closed_reports_count = 0

    return closed_reports_count

def count_open_reports_last_week():
    # Get the current date and calculate the date one week ago
    current_date = datetime.now()
    one_week_ago = current_date - timedelta(days=7)

    # Perform the aggregation query
    pipeline = [
        {
            '$match': {
                'Open_Date': {
                    '$gte': one_week_ago,
                    '$lte': current_date
                }
            }
        },
        {
            '$count': 'open_reports_last_week'
        }
    ]

    result = list(Reports_collections.aggregate(pipeline))

    # Extract the count from the result
    if result:
        open_reports_count = result[0]['open_reports_last_week']
    else:
        open_reports_count = 0

    return open_reports_count


def count_open_reports_last_3month():
    # Get the current date and calculate the date three months ago
    current_date = datetime.now()
    three_month_ago = current_date - timedelta(days=93)

    # Perform the aggregation query
    pipeline = [
        {
            '$match': {
                'Open_Date': {
                    '$gte': three_month_ago,
                    '$lte': current_date
                },
                'Report_Type': 'Bag'  # Only count reports with Report_Type = 'Bag'
            }
        },
        {
            '$count': 'open_reports_last_3month'
        }
    ]

    result = list(Reports_collections.aggregate(pipeline))

    # Extract the count from the result
    if result:
        open_reports_count = result[0]['open_reports_last_3month']
    else:
        open_reports_count = 0

    return round(open_reports_count / 3)




def bag_report_vs_area():
    bag_report_count = list(client['Doggy_Doo']['Reports'].aggregate([
        {'$match': {'Report_Type': 'Bag'}},
        {'$count': 'count'}
    ]))

    area_report_count = list(client['Doggy_Doo']['Reports'].aggregate([
        {'$match': {'Report_Type': 'Area'}},
        {'$count': 'count'}
    ]))

    # Extract the counts or set to 0 if not found
    bag_count = bag_report_count[0]['count'] if bag_report_count else 0
    area_count = area_report_count[0]['count'] if area_report_count else 0

    return bag_count, area_count

def avg_days_open(reports):
    # print(f"Total reports received: {len(reports)}")  # Print the total number of reports
    total_duration = 0
    count = 0

    for report in reports:
        # Ensure 'Open_Date' and 'Close_Date' are datetime objects
        Open_Date = report.get('Open_Date')
        Close_Date = report.get('Close_Date')

        if isinstance(Open_Date, datetime):
            if isinstance(Close_Date, datetime):
                # Calculate duration between Open_Date and Close_Date
                duration = Close_Date - Open_Date
            else:
                # Calculate duration from Open_Date to the current date
                duration = datetime.now() - Open_Date

            duration_days = duration.total_seconds() / (60 * 60 * 24)  # Convert seconds to days

            # Print _id and duration for each report
            # print(f"Report ID: {report.get('_id')}, Duration: {duration_days:.2f} days")

            total_duration += duration.total_seconds()
            count += 1

    if count > 0:
        average_duration_seconds = total_duration / count
        average_duration_days = average_duration_seconds / (60 * 60 * 24)  # Convert seconds to days
        return average_duration_days
    else:
        return 0

def dashboard(request):
    employees = list(Employees_collections.find({}))
    stations = list(Bag_Stations_collections.find({}))
    reports = list(Reports_collections.find({}))
    empty_station_query = list(client['Doggy_Doo']['Bag_Stations'].aggregate([
        {
            '$project': {
                '_id': 1,
                'Bags_Status': 1
            }
        }, {
            '$match': {
                'Bags_Status': 'empty'
            }
        }, {
            '$count': 'Total Empty Stations'
        }
    ]))
    open_report_query = list(client['Doggy_Doo']['Reports'].aggregate([
        {
            '$match': {
                '$or': [
                    {'Close_Date': {'$exists': False}},
                    {'Close_Date': None}
                ]
            }
        },

        {
            '$count': 'distinct_reports_without_close_date'
        }
    ]))


    avg_days=round(avg_days_open(reports))
    open_report_past_week =count_open_reports_last_week()
    stations_with_reports = get_top_stations_with_reports()
    closed_report_open_past_week=count_closed_report_last_week()
    count_reports_per_employee=get_top_empolyees_with_reports()
    avg_time_to_open=avg_time_between_reports()
    bag_count, area_count = bag_report_vs_area()
    # print(f"Average duration a report is open: {avg_days:.2f} days")

    empty_stations_count = empty_station_query[0]['Total Empty Stations'] if empty_station_query else 0
    open_report_count = open_report_query[0]['distinct_reports_without_close_date'] if open_report_query else 0

    return render(request,"manager-dashboard.html",{'employees': employees,'stations':stations,'empty_stations_count': empty_stations_count,
                                                    'open_report_query':open_report_count,'avg_days':avg_days,'open_report_past_week':open_report_past_week,
                                                    'closed_report_open_past_week':closed_report_open_past_week,'reports_per_station': stations_with_reports,
                                                    'count_reports_per_employee':count_reports_per_employee,'avg_time_to_open':avg_time_to_open,
                                                    'bag_count': bag_count,'area_count': area_count})


def update_neighbors_in_mongodb(max_distance):
    stations = list(Bag_Stations_collections.find())
    RADIUS_LIMIT = max_distance  # 300 meters

    for station in stations:
        station_id = station['_id']
        station_coordinates = station['location_coordinates']

        # Initialize neighbors list for the current station
        neighbors_list = []

        for other_station in stations:
            if other_station['_id'] != station_id:
                other_station_id = other_station['_id']
                other_station_coordinates = other_station['location_coordinates']
                distance = haversine_distance(station_coordinates, other_station_coordinates)

                if distance < RADIUS_LIMIT:
                    # Add the other station to the neighbors list
                    neighbors_list.append({
                        'station_id': other_station_id,
                        'distance': distance,
                        'Bags_Status': other_station.get('Bags_Status', 'Unknown'),
                        'address': other_station.get('address', 'Unknown')
                    })

                    # Ensure the current station is also in the other station's neighbors list
                    Bag_Stations_collections.update_one(
                        {'_id': other_station_id},
                        {'$addToSet': {'neighbors': {
                            'station_id': station_id,
                            'distance': distance,
                            'Bags_Status': station.get('Bags_Status', 'Unknown'),
                            'address': station.get('address', 'Unknown')
                        }}}
                    )

        # Update the current station's neighbors in MongoDB
        Bag_Stations_collections.update_one(
            {'_id': station_id},
            {'$set': {'neighbors': neighbors_list}}
        )


def find_station(request, station_id):
    # Find all stations except the current one, which have a defined address and are not empty
    stations = Bag_Stations_collections.find({
        'Bags_Status': {'$ne': 'empty'},
        '_id': {'$ne': ObjectId(station_id)},
        'address': {'$exists': True}
    })

    # Find the current station's coordinates
    current_station = Bag_Stations_collections.find_one({'_id': ObjectId(station_id)},
                                                        {'location_coordinates': 1, '_id': 0})
    location_coordinates1 = current_station['location_coordinates']

    # Calculate 48 hours ago from the current time
    now = datetime.now()
    time_limit = now - timedelta(hours=48)

    stations_for_web = []
    for station in stations:
        if 'location_coordinates' in station:
            station['distance_from_station1'] = haversine_distance(location_coordinates1,
                                                                   station['location_coordinates'])
        else:
            station['distance_from_station1'] = "-"

        # Calculate the empty_neighbors_ratio
        neighbors = station.get('neighbors', [])
        empty_neighbors_count = sum(1 for neighbor in neighbors if neighbor.get('Bags_Status') == 'empty')
        total_neighbors_count = len(neighbors)
        empty_neighbors_ratio = (
                    empty_neighbors_count / total_neighbors_count * 100) if total_neighbors_count > 0 else 0

        # Check the last handling date
        last_handling_date = Reports_Handling_collections.find_one(
            {'Station_id': station['_id']},
            sort=[('Handling_Date', -1)],  # Sort by Handling_Date descending
            projection={'Handling_Date': 1, '_id': 0}
        )

        if last_handling_date:
            last_handling_date = last_handling_date['Handling_Date']
            # Ensure last_handling_date is a datetime object
            if isinstance(last_handling_date, str):
                last_handling_date = datetime.strptime(last_handling_date, '%Y-%m-%d')  # Adjust format if necessary
        else:
            last_handling_date = datetime.min  # Default to the earliest possible date if none found

        # Filter stations based on empty_neighbors_ratio and last_handling_date
        if empty_neighbors_ratio < 70 and last_handling_date > time_limit:
            stations_for_web.append(station)

    # Sort by distance from the current station
    stations_for_web.sort(key=lambda x: x['distance_from_station1'])

    if current_station:
        return render(request, 'ChooseClosestStation.html',
                      {'stations': stations_for_web, 'current_station': current_station})


def haversine_distance(loc1, loc2):
    R = 6371.0  # Radius of the Earth in kilometers

    # Extract latitude and longitude from loc1 and loc2
    lat1, lng1 = math.radians(loc1['lat']), math.radians(loc1['lng'])
    lat2, lng2 = math.radians(loc2['lat']), math.radians(loc2['lng'])

    # Haversine formula
    dlat = lat2 - lat1
    dlng = lng2 - lng1
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlng / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    distance = R * c * 1000
    distance_rounded = int(round(distance, 0))
    return distance_rounded

def check_user(request):
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")
        station_id = request.POST.get("station_id")

        # Query MongoDB to find the user with given username and password
        user = Employees_collections.find_one({'User_Name': username, 'Password': password})

        if user:
            return redirect('Report_Handle', station_id=station_id, employee_id=str(user['_id']))
            # print(user.id)
        else:
            error_message = 'Invalid username or password.'
            return render(request, 'Login.html', {'error': error_message, 'station_id': station_id})
    else:
        return render(request, 'Login.html')  # Render the login form initially


def report_view(request):
    if request.method == 'POST':
        form = ReportForm(request.POST)
        if form.is_valid():
            name = form.cleaned_data['name']
            email = form.cleaned_data['email']
            phone = form.cleaned_data['phone']
            station_id = request.POST.get('station_id')
            print("1")
            image = request.FILES.get('image')
            if image:
                image_name = default_storage.save(image.name, image)
                image_url = default_storage.url(image_name)
            print("2")
            if not station_id:
                return JsonResponse({"message": "Station ID is missing."})

            station = Bag_Stations_collections.find_one({"_id": ObjectId(station_id)})

            if station:
                if 'Bags_Status' in station:
                    if station['Bags_Status'] == 'not empty':
                        Bag_Stations_collections.update_one({"_id": ObjectId(station_id)},
                                                            {"$set": {"Bags_Status": "empty"}})
                        status_message = "הדיווח הושלם בהצלחה."

                        new_report = {
                            "_id": ObjectId(),
                            "Open_Date": datetime.now(),
                            "Report_Type": "Bag",
                            "reporter_name": name,
                            "station_id": ObjectId(station_id)
                        }
                        if email:
                            new_report["email"] = email
                        if phone:
                            new_report["phone"] = phone

                        Reports_collections.insert_one(new_report)

                        return JsonResponse({"message": status_message})
                    else:
                        status_message = "קיים דיווח על עמדה זו במערכת."
                        return JsonResponse({"message": status_message})
                else:
                    status_message = "Bags_Status key is missing in the station document."
                    return JsonResponse({"message": status_message})
            else:
                return JsonResponse({"message": "Station not found."})
        else:
            return JsonResponse({"message": "הטופס לא תקין."})
    else:
        return JsonResponse({"message": "בקשה לא תקינה."})

def contact_view(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        email = request.POST.get('email')
        phone = request.POST.get('phone')
        message = request.POST.get('message')

        if not name:
            return JsonResponse({"message": "שם הוא שדה חובה."})

        if not email and not phone:
            return JsonResponse({"message": "חובה להשאיר אימייל או מספר טלפון."})

        new_contact = {
            "_id": ObjectId(),
            "name": name,
            "email": email,
            "phone": phone,
            "message": message,
            "date": datetime.now()
        }

        Reports_collections.insert_one(new_contact)

        return JsonResponse({"message": "נוצרה פנייה למוקד 106 של הערייה והיא תטופל בהקדם."})
    else:
        return JsonResponse({"message": "בקשה לא תקינה."})

#


def update_status(request):
    if request.method == 'POST':
        data = json.loads(request.body.decode('utf-8'))
        station_id = data.get('station_id')
        report_type = data.get('report_type')
        action = data.get('action')
        employee_id = data.get('employee_id')

        if not station_id:
            return JsonResponse({"message": "Station ID is missing."})

        station = Bag_Stations_collections.find_one({"_id": ObjectId(station_id)})

        if station:
            if report_type == 'Bag' and action == 'fill':
                if 'Bags_Status' in station:
                    if station['Bags_Status'] == 'empty':
                        Bag_Stations_collections.update_one({"_id": ObjectId(station_id)},
                                                            {"$set": {"Bags_Status": "not empty"}})
                        report = Reports_collections.find_one_and_update(
                            {"station_id": ObjectId(station_id), "Report_Type": "Bag", "Close_Date": {"$exists": False}},
                            {"$set": {"Close_Date": datetime.now()}}
                        )
                        report_id = report['_id'] if report else None

                        # הוספת רשומה חדשה ל-Report_Handling
                        handling_record = {
                            "Employee_id": ObjectId(employee_id),
                            "Station_id": ObjectId(station_id),
                            "Handling_Date": datetime.now(),
                            "Handling_Type": "Bag",
                            "Report_id": report_id
                        }
                        Reports_Handling_collections.insert_one(handling_record)
                        local_authority_name = station.get('Local_Authority_name')
                        if local_authority_name:
                            Local_Authority_collections.update_one(
                                {"Local_Authority_name": local_authority_name},
                                {"$inc": {"Stock_bags": -1}}
                            )
                        return JsonResponse({"message": "הדיווח טופל בהצלחה."})
                    else:
                        return JsonResponse({"message": "עמדה זו כבר מסומנת כמלאה."})
                else:
                    return JsonResponse({"message": "Bags_Status key is missing in the station document."})

            elif report_type == 'Area' and action == 'clean':
                if 'Dirty_Area' in station:
                    if station['Dirty_Area'] == 'dirty':
                        Bag_Stations_collections.update_one({"_id": ObjectId(station_id)},
                                                            {"$set": {"Dirty_Area": "clean"}})
                        report = Reports_collections.find_one_and_update(
                            {"station_id": ObjectId(station_id), "Report_Type": "Area", "Close_Date": {"$exists": False}},
                            {"$set": {"Close_Date": datetime.now()}}
                        )
                        report_id = report['_id'] if report else None

                        # הוספת רשומה חדשה ל-Report_Handling
                        handling_record = {
                            "Employee_id": ObjectId(employee_id),
                            "Station_id": ObjectId(station_id),
                            "Handling_Date": datetime.now(),
                            "Handling_Type": "Area",
                            "Report_id": report_id
                        }
                        Reports_Handling_collections.insert_one(handling_record)

                        return JsonResponse({"message": "הדיווח טופל בהצלחה."})


                    else:
                        return JsonResponse({"message": "האזור כבר מסומן כנקי."})
                else:
                    return JsonResponse({"message": "Dirty_Area key is missing in the station document."})
            else:
                return JsonResponse({"message": "Invalid report type or action."})
        else:
            return JsonResponse({"message": "Station not found."})
    else:
        return JsonResponse({"message": "בקשה לא תקינה."})
#

def employee_list(request):
    employees = list(Employees_collections.find())
    for employee in employees:
        employee['id'] = str(employee.pop('_id'))  # Convert ObjectId to string and rename
    return render(request, 'CreateEmployee.html', {'employees': employees})

def delete_employee(request, employee_id):
    Employees_collections.delete_one({'_id': ObjectId(employee_id)})
    return redirect('employees')


def add_employee(request):
    if request.method == 'POST':
        first_name = request.POST['first_name']
        last_name = request.POST['last_name']
        phone_number = request.POST['phone_number']
        email = request.POST['email']
        user_name = request.POST['user_name']
        password = request.POST['password1']
        employee_type = request.POST['employee_type']

        employee_data = {
            'First_Name': first_name,
            'Last_Name': last_name,
            'Employee_Phone_Number': phone_number,
            'Employee_Mail': email,
            'User_Name': user_name,
            'Password': password,
            'Employee_Type': employee_type
        }

        Employees_collections.insert_one(employee_data)
        return redirect('employees')

    return render(request, 'employees')

def edit_employee(request, employee_id):
    employee = Employees_collections.find_one({'_id': ObjectId(employee_id)})
    if not employee:
        return redirect('employees')

    if request.method == 'POST':
        updated_data = {
            'First_Name': request.POST['first_name'],
            'Last_Name': request.POST['last_name'],
            'Employee_Phone_Number': request.POST['phone_number'],
            'Employee_Mail': request.POST['email'],
            'User_Name': request.POST['user_name'],
            'Password': request.POST['password1'],
            'Employee_Type': request.POST['employee_type']
        }

        Employees_collections.update_one({'_id': ObjectId(employee_id)}, {'$set': updated_data})
        return redirect('employees')

    employee['id'] = str(employee.pop('_id'))  # Convert ObjectId to string and rename
    return render(request, 'edit_employee.html', {'employee': employee})



def report_view(request):
    if request.method == 'POST':
        form = ReportForm(request.POST)
        if form.is_valid():
            name = form.cleaned_data['name']
            email = form.cleaned_data['email']
            phone = form.cleaned_data['phone']
            station_id = request.POST.get('station_id')
            report_type = request.POST.get('report_type')
            image = request.FILES.get('image')
            if image:
                image_name = default_storage.save(image.name, image)
                image_url = default_storage.url(image_name)
            # print(f"Received station_id: {station_id}")  # הדפסת ID העמדה
            # print(f"Report type: {report_type}")  # הדפסת סוג הדיווח

            if not station_id:
                return JsonResponse({"message": "Station ID is missing."})

            station = Bag_Stations_collections.find_one({"_id": ObjectId(station_id)})
            # print(f"Station data: {station}")  # הדפסת כל הנתונים של העמדה

            if station:
                if report_type == 'Bag':
                    if 'Bags_Status' in station:
                        # print(f"Current Bags_Status: {station['Bags_Status']}")  # הדפסת הסטטוס הנוכחי
                        if station['Bags_Status'] == 'not empty':
                            Bag_Stations_collections.update_one({"_id": ObjectId(station_id)},
                                                                {"$set": {"Bags_Status": "empty"}})
                            status_message = "הדיווח הושלם בהצלחה."

                            new_report = {
                                "_id": ObjectId(),
                                "Open_Date": datetime.now(),
                                "Report_Type": "Bag",
                                "reporter_name": name,
                                "station_id": ObjectId(station_id)
                            }
                            if email:
                                new_report["email"] = email
                            if phone:
                                new_report["phone"] = phone

                            Reports_collections.insert_one(new_report)
                            # print(f"Report added with id: {new_report['_id']}")  # הדפסת ה-ID של הדיווח החדש

                            return JsonResponse({"message": status_message})
                        else:
                            status_message = "קיים דיווח על עמדה זו במערכת."
                            return JsonResponse({"message": status_message})
                    else:
                        status_message = "Bags_Status key is missing in the station document."
                        return JsonResponse({"message": status_message})

                elif report_type == 'Area':
                    if 'Dirty_Area' in station:
                        # print(f"Current Dirty_Area: {station['Dirty_Area']}")  # הדפסת הסטטוס הנוכחי
                        if station['Dirty_Area'] == 'clean':
                            Bag_Stations_collections.update_one({"_id": ObjectId(station_id)},
                                                                {"$set": {"Dirty_Area": "dirty"}})
                            status_message = "הדיווח הושלם בהצלחה."

                            new_report = {
                                "_id": ObjectId(),
                                "Open_Date": datetime.now(),
                                "Report_Type": "Area",
                                "reporter_name": name,
                                "station_id": ObjectId(station_id)
                            }
                            if email:
                                new_report["email"] = email
                            if phone:
                                new_report["phone"] = phone
                            if image:
                                new_report["image_url"] = image_url
                            Reports_collections.insert_one(new_report)
                            # print(f"Report added with id: {new_report['_id']}")  # הדפסת ה-ID של הדיווח החדש

                            return JsonResponse({"message": status_message})
                        else:
                            status_message = "קיים דיווח על אזור זה במערכת."
                            return JsonResponse({"message": status_message})
                    else:
                        status_message = "Dirty_Area key is missing in the station document."
                        return JsonResponse({"message": status_message})

            else:
                return JsonResponse({"message": "Station not found."})
        else:
            return JsonResponse({"message": "הטופס לא תקין."})
    else:
        return JsonResponse({"message": "בקשה לא תקינה."})


def contact_view(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        email = request.POST.get('email')
        phone = request.POST.get('phone')
        message = request.POST.get('message')

        if not name:
            return JsonResponse({"message": "שם הוא שדה חובה."})

        if not email and not phone:
            return JsonResponse({"message": "חובה להשאיר אימייל או מספר טלפון."})

        new_contact = {
            "_id": ObjectId(),
            "name": name,
            "email": email,
            "phone": phone,
            "message": message,
            "date": datetime.now()
        }

        Reports_collections.insert_one(new_contact)

        return JsonResponse({"message": "תודה על פנייתך. נפתחה פנייה במוקד הערייה והיא תטופל בהקדם האפשרי."})
    else:
        return JsonResponse({"message": "בקשה לא תקינה."})


def stations_list(request):
    # Find and sort stations by 'Area' field in ascending order (1 for ascending, -1 for descending)
    stations = list(Bag_Stations_collections.find().sort('Area', -1))

    # Convert ObjectId to string and rename '_id' to 'id'
    for station in stations:
        station['id'] = str(station.pop('_id'))  # Convert ObjectId to string and rename

    # Render the template and pass the ordered stations list
    return render(request, 'Stations.html', {'stations': stations})

def delete_station(request, station_id):
    Bag_Stations_collections.delete_one({'_id': ObjectId(station_id)})
    return redirect('stations')

def add_station(request):
    if request.method == 'POST':
        Local_Authority_name = "תל אביב"
        Bags_Status = "not empty"
        Dirty_Area = "clean"
        Area=request.POST['Area']
        lat=request.POST['lat']
        lng = request.POST['lng']
        address = request.POST['address']

        station_data = {
            'Local_Authority_name': Local_Authority_name,
            'Bags_Status': Bags_Status,
            'Dirty_Area': Dirty_Area,
            'Area': Area,
            'location_coordinates':{'lat':float(lat),'lng':float(lng)},
            'address': address
        }

        Bag_Stations_collections.insert_one(station_data)
        return redirect('stations')

    return render(request, 'stations')

def edit_station(request, station_id):
    station = Bag_Stations_collections.find_one({'_id': ObjectId(station_id)})
    if not station:
        return redirect('stations')

    if request.method == 'POST':
        updated_data = {
                    'Local_Authority_name' : request.POST["Local_Authority_name"],
                    # 'Bags_Status' : "not empty",
                    # 'Dirty_Area' : "clean",
                   'Area':request.POST['Area'],
                    'location_coordinates':{'lat':float(request.POST['lat']),'lng':float(request.POST['lng'])},
                    'address':request.POST['address']

                }

        Bag_Stations_collections.update_one({'_id': ObjectId(station_id)}, {'$set': updated_data})
        return redirect('stations')

    station['id'] = str(station.pop('_id'))  # Convert ObjectId to string and rename
    return render(request, 'edit_station.html', {'station': station})