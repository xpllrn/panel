from rest_framework.decorators import api_view
from rest_framework.response import Response


@api_view(["GET"])
def api_info(request):
    """API information endpoint"""
    return Response(
        {
            "message": "Admin Panel API",
            "version": "1.0.0",
            "endpoints": {
                "info": "/api/",
                "docs": "/api/docs/",
            },
        }
    )
