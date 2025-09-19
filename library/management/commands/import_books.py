import csv
import os
from django.core.management.base import BaseCommand
from library.models import Category, Book

# ----- pluralize words e.g. copy ------ #
def pluralize(word, count):
    if count == 1:
        return word
    if word.endswith("y"):
        return word[:-1] + "ies"
    return word + "s"

class Command(BaseCommand):
    help = "Import books from one or more CSV files into the database"

    def add_arguments(self, parser):
        parser.add_argument(
            "csv_files",
            nargs="*",
            type=str,
            help="Path(s) to one or more CSV files",
        )
        parser.add_argument(
            "--folder",
            type=str,
            help="Optional folder containing CSV files to import",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Preview the changes without saving to the database",
        )

    def handle(self, *args, **kwargs):
        dry_run = kwargs["dry_run"]
        folder_path = kwargs.get("folder")
        csv_files = kwargs["csv_files"] if kwargs.get("csv_files") else []

        # Collect files from folder, if provided
        if folder_path:
            if not os.path.isdir(folder_path):
                self.stdout.write(self.style.ERROR(f"Folder not found: {folder_path}"))
                return
            folder_csvs = [
                os.path.join(folder_path, f)
                for f in os.listdir(folder_path)
                if f.lower().endswith(".csv")
            ]
            csv_files.extend(folder_csvs)

        if not csv_files:
            self.stdout.write(self.style.ERROR("No CSV files provided or found in folder."))
            return

        # Totals across all files
        total_added, total_updated, total_skipped = 0, 0, 0
        total_updated_books = []
        total_skipped_rows = []

        for csv_file in csv_files:
            self.stdout.write(self.style.NOTICE(f"\n=== Processing file: {csv_file} ==="))

            added, updated, skipped = 0, 0, 0
            updated_books = []
            skipped_rows = []

            try:
                with open(csv_file, newline="", encoding="utf-8") as f:
                    reader = csv.DictReader(f)

                    for row in reader:
                        category_name = row["CATEGORY"].strip()
                        book_code = row["BOOK CODE"].strip()
                        title = row["BOOK TITLE"].strip()
                        authors = row["BOOK AUTHOR"].strip() if row["BOOK AUTHOR"] else None
                        number_of_copies = row["NO. OF COPIES"].strip()

                        # 1. Skip rows with no title
                        if not title:
                            self.stdout.write(self.style.WARNING(f"Skipping row with missing title: {row}"))
                            skipped += 1
                            skipped_rows.append((category_name, book_code))
                            continue

                        # Ensure category exists
                        category, _ = Category.objects.get_or_create(name=category_name)

                        # 2. Default to 1 if missing/invalid
                        try:
                            copies = int(number_of_copies)
                        except (TypeError, ValueError):
                            copies = 1

                        if dry_run:
                            try:
                                existing = Book.objects.get(book_code=book_code)
                                changes = []
                                if existing.title != title:
                                    changes.append(f"Title: '{existing.title}' → '{title}'")
                                if existing.authors != authors:
                                    changes.append(f"Authors: '{existing.authors}' → '{authors}'")
                                if existing.category.name != category.name:
                                    changes.append(f"Category: '{existing.category.name}' → '{category.name}'")
                                if existing.number_of_copies != copies:
                                    changes.append(f"Copies: {existing.number_of_copies} → {copies}")

                                if changes:
                                    updated += 1
                                    updated_books.append(book_code)
                                    self.stdout.write(self.style.NOTICE(
                                        f"[DRY RUN] Would UPDATE {book_code}:"
                                    ))
                                    for change in changes:
                                        self.stdout.write(f"   - {change}")
                                else:
                                    skipped += 1
                                    self.stdout.write(self.style.WARNING(
                                        f"[DRY RUN] Would SKIP {book_code} (no changes)"
                                    ))
                            except Book.DoesNotExist:
                                added += 1
                                self.stdout.write(self.style.SUCCESS(
                                    f"[DRY RUN] Would ADD {book_code} - {title} by {authors or 'Unknown'} "
                                    f"({copies} {pluralize('copy', copies)}) in {category.name}"
                                ))
                            continue

                        # 3. Insert or update
                        obj, created = Book.objects.update_or_create(
                            book_code=book_code,
                            defaults={
                                "category": category,
                                "title": title,
                                "authors": authors,
                                "number_of_copies": copies,
                            },
                        )

                        if created:
                            self.stdout.write(self.style.SUCCESS(f"Added new book: {obj}"))
                            added += 1
                        else:
                            self.stdout.write(self.style.NOTICE(f"Updated existing book: {obj}"))
                            updated += 1
                            updated_books.append(str(obj))
            except FileNotFoundError:
                self.stdout.write(self.style.ERROR(f"File not found: {csv_file}"))
                continue
            except KeyError as e:
                self.stdout.write(self.style.ERROR(f"Missing expected column {e} in {csv_file}"))
                continue

            # File summary
            self.stdout.write(self.style.SUCCESS(f"\n✔ {added} {pluralize('book', added)} added from {csv_file}"))
            self.stdout.write(self.style.NOTICE(f"✔ {updated} {pluralize('book', updated)} updated"))
            self.stdout.write(self.style.WARNING(f"✔ {skipped} {pluralize('row', skipped)} skipped"))

            if updated_books:
                self.stdout.write(self.style.NOTICE("\nUpdated entries:"))
                for book in updated_books:
                    self.stdout.write(f" - {book}")

            if skipped_rows:
                self.stdout.write(self.style.WARNING("\nSkipped rows (missing title):"))
                for cat, code in skipped_rows:
                    self.stdout.write(f" - Category: {cat} | Book Code: {code}")

            # Accumulate totals
            total_added += added
            total_updated += updated
            total_skipped += skipped
            total_updated_books.extend(updated_books)
            total_skipped_rows.extend(skipped_rows)

        # Final summary
        self.stdout.write(self.style.NOTICE("\n=== Final Summary ==="))
        self.stdout.write(self.style.SUCCESS(f"Total Added:   {total_added} {pluralize('book', total_added)}"))
        self.stdout.write(self.style.NOTICE(f"Total Updated: {total_updated} {pluralize('book', total_updated)}"))
        self.stdout.write(self.style.WARNING(f"Total Skipped: {total_skipped} {pluralize('row', total_skipped)}"))

        if total_updated_books:
            self.stdout.write(self.style.NOTICE("\nAll updated entries:"))
            for book in total_updated_books:
                self.stdout.write(f" - {book}")

        if total_skipped_rows:
            self.stdout.write(self.style.WARNING("\nAll skipped rows (missing title):"))
            for cat, code in total_skipped_rows:
                self.stdout.write(f" - Category: {cat} | Book Code: {code}")
