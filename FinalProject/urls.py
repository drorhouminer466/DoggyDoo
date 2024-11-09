"""
URL configuration for djangoProject project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.urls import path
from DoogyDoo import views

urlpatterns = [
    #path('admin/', admin.site.urls),
    path("",views.managerLogin,name="managerLogin"),
    path("employees/",views.employee_list,name="employees"),
    path('delete_employee/<str:employee_id>/', views.delete_employee, name='delete_employee'),
    path('add_employee/', views.add_employee, name='add_employee'),
    path('edit_employee/<str:employee_id>/', views.edit_employee, name='edit_employee'),
    path("stations/",views.stations_list,name="stations"),
    path('delete_station/<str:station_id>/', views.delete_station, name='delete_station'),
    path('add_station/', views.add_station, name='add_station'),
    path('edit_station/<str:station_id>/', views.edit_station, name='edit_station'),
    path("login/<str:station_id>",views.login,name="mainPage"),
    path("check_user/",views.check_user,name="check_user"),
    path("mainwindow/<str:station_id>", views.mainwindow, name="mainwindow"),
    path("Report_Handle/<str:station_id>/<str:employee_id>", views.Report_Handle, name="Report_Handle"),
    path('report/', views.report_view, name='report_view'),
    path('contact/', views.contact_view, name='contact_view'),
    path('update_status/', views.update_status, name='update_status'),
    path("findstation/<str:station_id>/",views.find_station,  name="ChooseClosestStation"),
    path("manager-dashboard/",views.dashboard,name="dashboard"),
    path("employeeAlert/",views.employeealert,name="employeeAlert"),
    path("route_map/",views.route_map,name="route_map"),
    path("managerAlert/",views.manageralert,name="managerAlert"),
    path("check_user_manager/", views.check_user_manager, name="check_user_manager"),
    path("neighbors/",views.update_neighbors_in_mongodb,name="neighbors")
    # path("missing_station/",)
]
