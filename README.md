# open_edx_api_extension

API extension for Open edX 

Installation
pip install -e git+https://github.com/raccoongang/open_edx_api_extension.git#egg=open_edx_api_extension

Add in file lms/envs/common.py
```python
INSTALLED_APPS = (
    ...
    'open_edx_api_extension',
)
```

Add in file lms/urls.py

```python
urlpatterns = (
    ...
    url(r'^api/extended/', include('open_edx_api_extension.urls'), namespace='api_extension'),
)
```