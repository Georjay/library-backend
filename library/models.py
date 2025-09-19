from django.db import models

class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name

class Book(models.Model):
    category = models.ForeignKey(Category, on_delete=models.CASCADE)
    book_code = models.CharField(max_length=50, unique=True)
    title = models.CharField(max_length=255)
    authors = models.CharField(max_length=255, blank=True, null=True)
    number_of_copies = models.PositiveIntegerField(default=1)

    def __str__(self):
        return f"{self.book_code} ({self.title})"

    @property
    def available(self):
        return self.number_of_copies > 0
    
    class Meta:
        ordering = ['id']

