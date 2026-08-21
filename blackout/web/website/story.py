# in blackout/web/website/story.py

from django.shortcuts import render

def storypage(request):
    return render(request, "story.html")