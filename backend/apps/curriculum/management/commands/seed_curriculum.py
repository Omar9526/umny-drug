"""Idempotent seed of the school curriculum catalogue and knowledge-map routes.

Safe to run repeatedly (``update_or_create`` on stable slugs) and in production: this is
reference data, not demo content. Topics removed from ``seed_data`` are *not* deleted, so
anything admins add by hand survives.
"""

from __future__ import annotations

import math

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import F

from apps.curriculum import seed_data
from apps.curriculum.models import Curriculum, Grade, Section, Subject, Topic
from apps.learning.models import KnowledgeMapNode


class Command(BaseCommand):
    help = "Seed the Kyrgyz school curriculum (subjects, sections, topics, knowledge map routes)."

    @transaction.atomic
    def handle(self, *args, **options):
        verbosity = int(options.get("verbosity", 1))
        curriculum, _ = Curriculum.objects.update_or_create(
            code=seed_data.CURRICULUM["code"],
            defaults={k: v for k, v in seed_data.CURRICULUM.items() if k != "code"},
        )

        grades: dict[int, Grade] = {}
        for number, (ru, ky) in seed_data.GRADE_NAMES.items():
            grades[number], _ = Grade.objects.update_or_create(
                curriculum=curriculum, number=number, defaults={"name_ru": ru, "name_ky": ky}
            )

        subjects: dict[str, Subject] = {}
        for row in seed_data.SUBJECTS:
            data = dict(row)
            slug = data.pop("slug")
            subjects[slug], _ = Subject.objects.update_or_create(
                curriculum=curriculum, slug=slug, defaults=data
            )

        sections_count = topics_count = nodes_count = 0
        for (subject_slug, grade_number), sections in seed_data.SECTIONS.items():
            subject = subjects[subject_slug]
            grade = grades[grade_number]
            route_topics: list[Topic] = []
            for order, (section_slug, ru, ky, topics) in enumerate(sections):
                section, _ = Section.objects.update_or_create(
                    subject=subject,
                    grade=grade,
                    slug=section_slug,
                    defaults={"name_ru": ru, "name_ky": ky, "order": order},
                )
                sections_count += 1
                for t_order, (topic_slug, t_ru, t_ky, difficulty, keywords) in enumerate(topics):
                    topic, _ = Topic.objects.update_or_create(
                        section=section,
                        slug=topic_slug,
                        defaults={
                            "name_ru": t_ru,
                            "name_ky": t_ky,
                            "order": t_order,
                            "difficulty": difficulty,
                            "keywords": keywords,
                            "is_active": True,
                        },
                    )
                    topics_count += 1
                    route_topics.append(topic)
            nodes_count += self._build_route(subject, grade, route_topics)

        if verbosity:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Curriculum '{curriculum.code}': {len(subjects)} subjects, {sections_count} sections, "
                    f"{topics_count} topics, {nodes_count} map nodes."
                )
            )

    @staticmethod
    def _build_route(subject: Subject, grade: Grade, topics: list[Topic]) -> int:
        """Lay the grade's topics out as a gentle winding path (a «learning journey»)."""
        route_key = f"{subject.slug}-{grade.number}"
        total = max(len(topics), 1)
        previous: KnowledgeMapNode | None = None
        existing = {node.topic_id: node for node in KnowledgeMapNode.objects.filter(route_key=route_key)}
        # Free the unique (route_key, order) slots before re-numbering (offset is undone below).
        KnowledgeMapNode.objects.filter(route_key=route_key).update(order=F("order") + 10_000)
        for order, topic in enumerate(topics):
            x = 50 + 32 * math.sin(order * 0.95)
            y = 100 * order / max(total - 1, 1)
            node = existing.get(topic.id)
            fields = {
                "subject": subject,
                "grade": grade,
                "parent": previous,
                "order": order,
                "x": round(x, 2),
                "y": round(y, 2),
                "icon": "map-pin",
            }
            if node is None:
                node = KnowledgeMapNode.objects.create(topic=topic, route_key=route_key, **fields)
            else:
                for key, value in fields.items():
                    setattr(node, key, value)
                node.save()
            previous = node
        # Nodes whose topics are no longer in the seed (or were added by admins) keep the route
        # but move behind the seeded ones, so repeated runs never overflow the order column.
        seeded_ids = {t.id for t in topics}
        orphans = [n for n in existing.values() if n.topic_id not in seeded_ids]
        for extra, node in enumerate(sorted(orphans, key=lambda n: n.order)):
            node.order = len(topics) + extra
            node.parent = previous
            node.save(update_fields=["order", "parent", "updated_at"])
        return len(topics)
