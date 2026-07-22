import pytest

LOGIN = "/api/v1/auth/login/"
ME = "/api/v1/auth/me/"
MANAGERS = "/api/v1/auth/managers/"


@pytest.mark.django_db
def test_health_check_is_public(api):
    resp = api().get("/api/v1/health/")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


@pytest.mark.django_db
@pytest.mark.parametrize("fixture,role", [("owner", "owner"), ("manager", "manager"), ("karigar_user", "karigar")])
def test_login_returns_token_and_role(api, request, fixture, role):
    user = request.getfixturevalue(fixture)
    resp = api().post(LOGIN, {"username": user.username, "password": "Karigar@123"})
    assert resp.status_code == 200, resp.content
    body = resp.json()
    assert body["access"] and body["refresh"]
    assert body["user"]["role"] == role


@pytest.mark.django_db
def test_login_rejects_bad_password(api, owner):
    resp = api().post(LOGIN, {"username": "owner", "password": "wrong"})
    assert resp.status_code == 401


@pytest.mark.django_db
def test_refresh_rotates(api, owner):
    tokens = api().post(LOGIN, {"username": "owner", "password": "Karigar@123"}).json()
    resp = api().post("/api/v1/auth/refresh/", {"refresh": tokens["refresh"]})
    assert resp.status_code == 200
    assert resp.json()["access"]


@pytest.mark.django_db
def test_me_requires_auth(api, manager):
    assert api().get(ME).status_code == 401
    resp = api(manager).get(ME)
    assert resp.status_code == 200
    assert resp.json()["username"] == "manager"


@pytest.mark.django_db
def test_only_owner_can_list_managers(api, owner, manager, karigar_user):
    assert api(manager).get(MANAGERS).status_code == 403
    assert api(karigar_user).get(MANAGERS).status_code == 403
    assert api(owner).get(MANAGERS).status_code == 200


@pytest.mark.django_db
def test_owner_creates_manager(api, owner):
    resp = api(owner).post(MANAGERS, {"username": "m2", "password": "Karigar@123", "full_name": "M2"})
    assert resp.status_code == 201, resp.content
    from apps.accounts.models import User
    assert User.objects.get(username="m2").role == "manager"


@pytest.mark.django_db
def test_change_calendar_setting(api, owner, manager, karigar_user):
    # Karigar can read but not change.
    assert api(karigar_user).get("/api/v1/auth/settings/").status_code == 200
    assert api(karigar_user).patch("/api/v1/auth/settings/", {"calendar_preference": "AD"}).status_code == 403
    resp = api(manager).patch("/api/v1/auth/settings/", {"calendar_preference": "AD"})
    assert resp.status_code == 200
    assert resp.json()["calendar_preference"] == "AD"
