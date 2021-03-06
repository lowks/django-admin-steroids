import importlib
import json
import operator

from django.views.generic.base import TemplateView
from django.http import HttpResponse
from django.core.exceptions import PermissionDenied
from django.core.cache import cache
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.db.models import Q

import utils

class ModelFieldSearchView(TemplateView):
    """
    Allows searching for field values in an arbitrary model for dynamically
    populating admin list filters.
    """

    @property
    def search_path_tuple(self):
        return (
            self.kwargs['app_name'],
            self.kwargs['model_name'],
            self.kwargs['field_name'],
        )

    @property
    def q(self):
        return self.request.GET.get('q', '').strip()

    @property
    def model(self):
#        mdls = importlib.import_module('%s.models' % self.kwargs['app_name'])
#        return getattr(mdls, self.kwargs['model_name'])
        ct = ContentType.objects.get(
            app_label=self.kwargs['app_name'],
            model=self.kwargs['model_name'])
        return ct.model_class()

#    def get_context_data(self, **kwargs):
#        context = super(HomePageView, self).get_context_data(**kwargs)
#        context['latest_articles'] = Article.objects.all()[:5]
#        return context

    @property
    def cache_key(self):
        return self.search_path_tuple + (self.q,)

    def render_to_response(self, context, **response_kwargs):

        path = self.search_path_tuple
        if path not in settings.DAS_ALLOWED_AJAX_SEARCH_PATHS:
            raise PermissionDenied

        # Ensure only authorized users can access admin URLs.
        #TODO:extend this to allow custom authentication options
        if 'admin' in self.request.path:
            if not self.request.user.is_authenticated():
                raise PermissionDenied
            elif not self.request.user.is_active:
                raise PermissionDenied
            elif not self.request.user.is_staff:
                raise PermissionDenied

        cache_key = self.cache_key
        response = cache.get(cache_key)
        if response:#TODO:enable
            return response

        model = self.model
        q = self.q
        field_name = self.kwargs['field_name']
        n = settings.DAS_MAX_AJAX_SEARCH_RESULTS
        results = []
        if q:
            field = model._meta.get_field(field_name)
            field_type = type(field)
            if isinstance(field, (models.CharField, models.EmailField, models.SlugField, models.TextField, models.URLField)):
                # Build query for a simple string-based field.
                qs = model.objects.filter(**{field_name+'__icontains': q})\
                    .values_list(field_name, flat=True)\
                    .order_by(field_name)\
                    .distinct()
                qs = qs[:n]
                results = [dict(key=_, value=_) for _ in qs]
            elif isinstance(field, (models.ForeignKey, models.ManyToManyField, models.OneToOneField)):
                # Build query for a related model.
                search_fields = settings.DAS_AJAX_SEARCH_PATH_FIELDS.get(path)
                if search_fields:
                    qs_args = []
                    for search_field in search_fields:
                        qs_args.append(Q(**{field_name+'__'+search_field+'__icontains': q}))
                    qs = model.objects.filter(reduce(operator.or_, qs_args))\
                        .values_list(field_name, flat=True)\
                        .order_by(field_name)\
                        .distinct()
                    qs = qs[:n]
                    rel_model = field.rel.to
                    results = [
                        dict(key=_, value=str(rel_model.objects.get(id=_)))
                        for _ in qs
                    ]

        response = HttpResponse(
            json.dumps(results),
            content_type='application/json',
            **response_kwargs
        )
        if settings.DAS_AJAX_SEARCH_DEFAULT_CACHE_SECONDS:
            cache.set(
                cache_key,
                response,
                settings.DAS_AJAX_SEARCH_DEFAULT_CACHE_SECONDS)
        return response
