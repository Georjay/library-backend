from rest_framework import serializers
from .models import Book

class BookSerializer(serializers.ModelSerializer):
    available = serializers.ReadOnlyField()

    class Meta:
        model = Book
        fields = ['id', 'category', 'book_code', 'title', 'authors', 'number_of_copies', 'available']