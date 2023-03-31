from swirl.processors.transform_query_processor import TransformQueryProcessorFactory
import swirl_server.settings as settings
import pytest
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from django.contrib.auth.models import User

import logging
## General and shared

@pytest.fixture
def api_client():
    return APIClient()

@pytest.fixture
def test_suser_pw():
    return 'password'

@pytest.fixture
def test_suser(test_suser_pw):
    return User.objects.create_user(
        username='admin',
        password=test_suser_pw,
        is_staff=True,  # Set to True if your view requires a staff user
        is_superuser=True,  # Set to True if your view requires a superuser
    )

class SearchTestCase(TestCase):
    @pytest.fixture(autouse=True)
    def _init_fixtures(self, api_client,test_suser, test_suser_pw):
        self._api_client = api_client
        self._test_suser = test_suser
        self._test_suser_pw = test_suser_pw

    def setUp(self):
        settings.CELERY_TASK_ALWAYS_EAGER = True

    def tearDown(self):
        settings.CELERY_TASK_ALWAYS_EAGER = False

    def test_query_search_viewset_search(self):
        is_logged_in = self._api_client.login(username=self._test_suser.username, password=self._test_suser_pw)
        # Check if the login was successful
        assert is_logged_in, 'Client login failed'
        # Call the viewset
        surl = reverse('search')
        # DN: FIX ME: finish this test, commented out now to avoid errors
        # response = self._api_client.get(surl, {'qs': 'notebook', 'pre_query_processor':'foo.bar'})

################################################################################
## individual cases

## Test fixtures
@pytest.fixture
def qrx_record_1():
    return {
        "name": "xxx",
        "shared": True,
        "qrx_type": "rewrite",
        "config_content": "# This is a test\n# column1, colum2\nmobiles; ombile; mo bile, mobile\ncheapest smartphones, cheap smartphone"
}

@pytest.fixture
def qrx_synonym():
    return {
        "name": "synonym 1",
        "shared": True,
        "qrx_type": "synonym",
        "config_content": "# column1, column2\nnotebook, laptop\nlaptop, personal computer\npc, personal computer\npersonal computer, pc"
}

@pytest.fixture
def qrx_synonym_bag():
    return {
        "name": "bag 1",
        "shared": True,
        "qrx_type": "bag",
        "config_content": "# column1....columnN\nnotebook, personal computer, laptop, pc\ncar,automobile, ride"
}
@pytest.fixture
def qrx_rewrite():
    return {
        "name": "rewrite 1",
        "shared": True,
        "qrx_type": "rewrite",
        "config_content": "# This is a test\n# column1, colum2\nmobiles; ombile; mo bile, mobile\ncheapest smartphones, cheap smartphone\non"
}
@pytest.fixture
def noop_query_string():
    return "noop"
######################################################################

@pytest.mark.django_db
def test_query_transform_allocation(noop_query_string, qrx_rewrite, qrx_synonym, qrx_synonym_bag):
    ret = TransformQueryProcessorFactory.alloc_query_transform(qrx_rewrite.get('qrx_type'),
                                        noop_query_string,
                                        qrx_rewrite.get('name'),
                                        qrx_rewrite.get('config_content'))
    assert str(ret) == 'RewriteQueryProcessor'

    ret = TransformQueryProcessorFactory.alloc_query_transform(qrx_synonym.get('qrx_type'),
                                        noop_query_string,
                                        qrx_rewrite.get('name'),
                                        qrx_rewrite.get('config_content'))
    assert str(ret) == 'SynonymQueryProcessor'

    ret = TransformQueryProcessorFactory.alloc_query_transform(qrx_synonym_bag.get('qrx_type'),
                                        noop_query_string,
                                        qrx_rewrite.get('name'),
                                        qrx_rewrite.get('config_content'))
    assert str(ret) == 'SynonymBagQueryProcessor'

######################################################################
@pytest.mark.django_db
def test_query_transform_synonym_parse(noop_query_string, qrx_synonym):
    sy_qxr = TransformQueryProcessorFactory.alloc_query_transform(qrx_synonym.get('qrx_type'),
                                        noop_query_string,
                                        qrx_synonym.get('name'),
                                        qrx_synonym.get('config_content'))
    assert str(sy_qxr) == 'SynonymQueryProcessor'
    sy_qxr.parse_config()
    rps = sy_qxr.get_replace_patterns()
    assert len(rps) == 4
    assert str(rps[0]) == "<<notebook>> -> <<['laptop']>>"
    assert str(rps[1]) == "<<laptop>> -> <<['personal computer']>>"
    assert str(rps[2]) == "<<pc>> -> <<['personal computer']>>"
    assert str(rps[3]) == "<<personal computer>> -> <<['pc']>>"

######################################################################

@pytest.mark.django_db
def test_query_transform_rewwrite_parse(noop_query_string, qrx_rewrite):
    rw_qxr = TransformQueryProcessorFactory.alloc_query_transform(qrx_rewrite.get('qrx_type'),
                                        noop_query_string,
                                        qrx_rewrite.get('name'),
                                        qrx_rewrite.get('config_content'))
    assert str(rw_qxr) == 'RewriteQueryProcessor'
    rw_qxr.parse_config()
    rps = rw_qxr.get_replace_patterns()
    assert len(rps) == 5
    assert str(rps[0]) == "<<mobiles>> -> <<['mobile']>>"
    assert str(rps[1]) == "<<ombile>> -> <<['mobile']>>"
    assert str(rps[2]) == "<<mo bile>> -> <<['mobile']>>"
    assert str(rps[3]) == "<<cheapest smartphones>> -> <<['cheap smartphone']>>"
    assert str(rps[4]) == '<<\\bon\\b\\s?>> -> <<[\'\']>>'

######################################################################
@pytest.mark.django_db
def test_query_transform_synonym_bag_parse(noop_query_string, qrx_synonym_bag):
    sy_qxr = TransformQueryProcessorFactory.alloc_query_transform(qrx_synonym_bag.get('qrx_type'),
                                        noop_query_string,
                                        qrx_synonym_bag.get('name'),
                                        qrx_synonym_bag.get('config_content'))
    assert str(sy_qxr) == 'SynonymBagQueryProcessor'
    sy_qxr.parse_config()
    rps = sy_qxr.get_replace_patterns()
    assert str(rps[0]) == "<<notebook>> -> <<['personal computer', 'laptop', 'pc']>>"
    assert str(rps[1]) == "<<personal computer>> -> <<['notebook', 'laptop', 'pc']>>"
    assert str(rps[2]) == "<<laptop>> -> <<['notebook', 'personal computer', 'pc']>>"
    assert str(rps[3]) == "<<pc>> -> <<['notebook', 'personal computer', 'laptop']>>"
    assert str(rps[4]) == "<<car>> -> <<['automobile', 'ride']>>"
    assert str(rps[5]) == "<<automobile>> -> <<['car', 'ride']>>"
    assert str(rps[6]) == "<<ride>> -> <<['car', 'automobile']>>"

@pytest.fixture
def qrx_rewrite_process():
    return {
        "name": "rewrite 1",
        "shared": True,
        "qrx_type": "rewrite",
        "config_content":
        """
# This is a test
# column1, colum2
mobiles; ombile; mo bile, mobile
computers, computer
cheap.* smartphones, cheap smartphone
on
"""
}
@pytest.fixture
def qrx_rewrite_test_queries():
    return ['mobile phone', 'mobiles','ombile', 'mo bile', 'on computing', 'cheaper smartphones','computers, go figure']

@pytest.fixture
def qrx_rewrite_expected_queries():
    return ['mobile phone', 'mobile','mobile', 'mobile', 'computing', 'cheap smartphone','computer go figure']
@pytest.mark.django_db
def test_query_transform_rewwrite_process(qrx_rewrite_test_queries, qrx_rewrite_expected_queries, qrx_rewrite_process):
    assert len(qrx_rewrite_test_queries) == len (qrx_rewrite_expected_queries)
    i = 0
    for q in qrx_rewrite_test_queries:
        rw_qxr = TransformQueryProcessorFactory.alloc_query_transform(qrx_rewrite_process.get('qrx_type'),
                                            q,
                                            qrx_rewrite_process.get('name'),
                                            qrx_rewrite_process.get('config_content'))
        assert str(rw_qxr) == 'RewriteQueryProcessor'
        ret = rw_qxr.process()
        assert ret == qrx_rewrite_expected_queries[i]
        i = i + 1

######################################################################
@pytest.fixture
def qrx_synonym_test_queries():
    return [
        '',
        'a',
        'robot human',
        'notebook',
        'pc',
        'personal computer',
        'I love my notebook',
        'This pc, it is better than a notebook',
        'My favorite song is "You got a fast car"'
        ]

@pytest.fixture
def qrx_synonym_expected_queries():
    return [
        '',
        'a',
        'robot human',
        '(notebook OR laptop)',
        '(pc OR personal computer)',
        '(personal computer OR pc)',
        'I love my (notebook OR laptop)',
        'This (pc OR personal computer) , it is better than a (notebook OR laptop)',
        'My favorite song is " You got a fast (car OR ride) "'
        ]

@pytest.fixture
def qrx_synonym_process():
    return {
        "name": "synonym 1",
        "shared": True,
        "qrx_type": "synonym",
        "config_content":
        """
# column1, column2
notebook, laptop
laptop, personal computer
pc, personal computer
personal computer, pc
car, ride
"""
}

@pytest.mark.django_db
def test_query_transform_synonym_process(qrx_synonym_test_queries, qrx_synonym_expected_queries, qrx_synonym_process):
    assert len(qrx_synonym_test_queries) == len(qrx_synonym_expected_queries)
    i = 0
    for q in qrx_synonym_test_queries:
        rw_qxr = TransformQueryProcessorFactory.alloc_query_transform(qrx_synonym_process.get('qrx_type'),
                                            q,
                                            qrx_synonym_process.get('name'),
                                            qrx_synonym_process.get('config_content'))
        assert str(rw_qxr) == 'SynonymQueryProcessor'
        ret = rw_qxr.process()
        assert ret == qrx_synonym_expected_queries[i]
        i = i + 1

@pytest.fixture
def qrx_synonym_bag_process():
    return {
        "name": "bag 1",
        "shared": True,
        "qrx_type": "bag",
        "config_content": """
# column1....columnN
notebook, personal computer, laptop, pc
car,automobile, ride
"""
}
######################################################################
@pytest.fixture
def qrx_synonym_bag_test_queries():
    return [
        '',
        'a',
        'machine human',
        'car',
        'automobile',
        'ride',
        'pimp my ride',
        'automobile, yours is fast',
        'I love the movie The Notebook',
        'My new notebook is slow'
        ]

@pytest.fixture
def qrx_synonym_bag_expected_queries():
    return [
        '',
        'a',
        'machine human',
        '(car OR automobile OR ride)',
        '(automobile OR car OR ride)',
        '(ride OR car OR automobile)',
        'pimp my (ride OR car OR automobile)',
        '(automobile OR car OR ride) , yours is fast',
        'I love the movie The Notebook',
        'My new (notebook OR personal computer OR laptop OR pc) is slow'
        ]

@pytest.mark.django_db
def test_query_transform_synonym_bag_process(qrx_synonym_bag_test_queries, qrx_synonym_bag_expected_queries, qrx_synonym_bag_process):
    assert len(qrx_synonym_bag_test_queries) == len(qrx_synonym_bag_expected_queries)
    i = 0
    for q in qrx_synonym_bag_test_queries:
        rw_qxr = TransformQueryProcessorFactory.alloc_query_transform(qrx_synonym_bag_process.get('qrx_type'),
                                            q,
                                            qrx_synonym_bag_process.get('name'),
                                            qrx_synonym_bag_process.get('config_content'))
        assert str(rw_qxr) == 'SynonymBagQueryProcessor'
        ret = rw_qxr.process()
        assert ret == qrx_synonym_bag_expected_queries[i]
        i = i + 1