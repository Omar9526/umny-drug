LANGUAGE_CHOICES = (("ru", "Русский"), ("ky", "Кыргызча"))

# Preset avatars for children: no uploads of real photos of minors.
AVATAR_KEYS = ("fox", "owl", "cat", "panda", "robot", "rocket", "star", "dino", "whale", "bee")
AVATAR_CHOICES = tuple((key, key) for key in AVATAR_KEYS)

# Family codes avoid ambiguous glyphs (0/O, 1/I/L).
FAMILY_CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
FAMILY_CODE_LENGTH = 6

PIN_MIN_LENGTH = 4
PIN_MAX_LENGTH = 6
