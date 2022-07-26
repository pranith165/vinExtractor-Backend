from django.urls import path
import default.views as views


app_name = 'users'

urlpatterns = [
    path('maps/', views.GetMaps, name='maps-apid'),
    # path('token/', views.CreateTokenView.as_view(), name='token'),
    # path('me/', views.ManageUserView.as_view(), name='me'),
]