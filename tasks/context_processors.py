def kolichestvo_neprochitannyh(request):
    if request.user.is_authenticated:
        return {'neprochitano': request.user.uvedomleniya.filter(prochitano=False).count()}
    return {'neprochitano': 0}