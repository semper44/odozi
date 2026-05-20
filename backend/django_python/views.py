from django.shortcuts import render

def dashboard_view(request):
    print("Dashboard view accessed")  # Debugging line to confirm the view is being hit
    # return render(request, "dashboard.html") 