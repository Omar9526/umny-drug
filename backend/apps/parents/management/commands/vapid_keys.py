from django.core.management.base import BaseCommand

from apps.parents import push


class Command(BaseCommand):
    help = (
        "Generate a VAPID key pair for Web Push and print the .env lines. Nothing is stored: paste the "
        "output into .env (or the secret store). Rotating the key invalidates every existing subscription."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--subject",
            default="mailto:ops@example.kg",
            help="Contact for push services (mailto: address or https:// URL), stored as VAPID_SUBJECT.",
        )

    def handle(self, *args, **options):
        private, public = push.generate_keypair()
        self.stdout.write("# Web Push (VAPID). Keep VAPID_PRIVATE_KEY secret.")
        self.stdout.write(f"VAPID_PRIVATE_KEY={private}")
        self.stdout.write(f"VAPID_PUBLIC_KEY={public}")
        self.stdout.write(f"VAPID_SUBJECT={options['subject']}")
