# Copyright (c) 2026, Safarwaala and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
import re


class Blog(Document):
    def before_save(self):
        self._auto_generate_slug()
        self._set_seo_defaults()
        self._set_reading_time()

    def _auto_generate_slug(self):
        """Auto-generate URL slug from title if not set."""
        if not self.slug and self.title:
            self.slug = self._slugify(self.title)

    def _slugify(self, text: str) -> str:
        text = text.lower().strip()
        text = re.sub(r"[^\w\s-]", "", text)
        text = re.sub(r"[\s_]+", "-", text)
        text = re.sub(r"-+", "-", text)
        return text

    def _set_seo_defaults(self):
        """Populate SEO fields from primary content if left blank."""
        if not self.seo_title:
            self.seo_title = self.title[:70] if self.title else ""

        if not self.meta_description and self.short_description:
            self.meta_description = self.short_description[:160]

        # Open Graph defaults
        if not self.og_title:
            self.og_title = self.seo_title or self.title
        if not self.og_description:
            self.og_description = self.meta_description or self.short_description
        if not self.og_image and self.thumbnail:
            self.og_image = self.thumbnail

        # Twitter defaults
        if not self.twitter_title:
            self.twitter_title = self.og_title
        if not self.twitter_description:
            self.twitter_description = self.og_description
        if not self.twitter_image and self.og_image:
            self.twitter_image = self.og_image

    def _set_reading_time(self):
        """Estimate reading time based on word count (~200 wpm)."""
        if self.content:
            # Strip HTML tags for word counting
            clean = re.sub(r"<[^>]+>", " ", self.content)
            words = len(clean.split())
            self.reading_time = max(1, round(words / 200))
