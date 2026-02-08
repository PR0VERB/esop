import common.validators
import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("tenants", "0001_initial"),
        ("beneficiaries", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Document",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "file",
                    models.FileField(
                        help_text="Uploaded file. Served only through authenticated download view.",
                        max_length=500,
                        upload_to=common.validators.get_upload_path,
                    ),
                ),
                (
                    "original_filename",
                    models.CharField(
                        help_text="Original filename as uploaded by the user.",
                        max_length=255,
                    ),
                ),
                (
                    "content_type",
                    models.CharField(
                        help_text="MIME type of the uploaded file.",
                        max_length=100,
                    ),
                ),
                (
                    "file_size",
                    models.PositiveIntegerField(
                        help_text="File size in bytes.",
                    ),
                ),
                (
                    "file_hash",
                    models.CharField(
                        blank=True,
                        help_text="SHA-256 hash of file contents for integrity verification.",
                        max_length=64,
                    ),
                ),
                ("title", models.CharField(max_length=255)),
                ("description", models.TextField(blank=True)),
                (
                    "category",
                    models.CharField(
                        choices=[
                            ("trust_deed", "Trust Deed"),
                            ("scheme_rules", "Scheme Rules"),
                            ("tax_certificate", "Tax Certificate"),
                            ("payment_file", "Payment File"),
                            ("board_resolution", "Board Resolution"),
                            ("beneficiary_id", "Beneficiary ID Document"),
                            ("beneficiary_proof", "Beneficiary Proof of Banking"),
                            ("dividend_report", "Dividend Report"),
                            ("month_end_report", "Month-End Report"),
                            ("sars_submission", "SARS Submission"),
                            ("other", "Other"),
                        ],
                        db_index=True,
                        default="other",
                        max_length=30,
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("quarantine", "Quarantine (pending scan)"),
                            ("active", "Active"),
                            ("archived", "Archived"),
                            ("rejected", "Rejected (failed scan)"),
                        ],
                        db_index=True,
                        default="quarantine",
                        max_length=20,
                    ),
                ),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="%(app_label)s_%(class)s_set",
                        to="tenants.company",
                    ),
                ),
                (
                    "beneficiary",
                    models.ForeignKey(
                        blank=True,
                        help_text="Beneficiary this document relates to (optional).",
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="documents",
                        to="beneficiaries.beneficiary",
                    ),
                ),
                (
                    "uploaded_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="uploaded_documents",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
                "abstract": False,
            },
        ),
        migrations.AddIndex(
            model_name="document",
            index=models.Index(
                fields=["company", "category"],
                name="documents_do_company_idx_cat",
            ),
        ),
        migrations.AddIndex(
            model_name="document",
            index=models.Index(
                fields=["company", "status"],
                name="documents_do_company_idx_sta",
            ),
        ),
        migrations.AddIndex(
            model_name="document",
            index=models.Index(
                fields=["beneficiary", "category"],
                name="documents_do_benefic_idx_cat",
            ),
        ),
    ]

