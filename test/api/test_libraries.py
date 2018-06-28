from base import api
from base.populators import (
    DatasetCollectionPopulator,
    DatasetPopulator,
    LibraryPopulator,
    TestsDatasets,
    wait_on_state
)


class LibrariesApiTestCase(api.ApiTestCase, TestsDatasets):

    def setUp(self):
        super(LibrariesApiTestCase, self).setUp()
        self.dataset_populator = DatasetPopulator(self.galaxy_interactor)
        self.dataset_collection_populator = DatasetCollectionPopulator(self.galaxy_interactor)
        self.library_populator = LibraryPopulator(self)

    def test_create(self):
        data = dict(name="CreateTestLibrary")
        create_response = self._post("libraries", data=data, admin=True)
        self._assert_status_code_is(create_response, 200)
        library = create_response.json()
        self._assert_has_keys(library, "name")
        assert library["name"] == "CreateTestLibrary"

    def test_delete(self):
        library = self.library_populator.new_library("DeleteTestLibrary")
        create_response = self._delete("libraries/%s" % library["id"], admin=True)
        self._assert_status_code_is(create_response, 200)
        library = create_response.json()
        self._assert_has_keys(library, "deleted")
        assert library["deleted"] is True
        # Test undeleting
        data = dict(undelete='true')
        create_response = self._delete("libraries/%s" % library["id"], data=data, admin=True)
        library = create_response.json()
        self._assert_status_code_is(create_response, 200)
        assert library["deleted"] is False

    def test_nonadmin(self):
        # Anons can't create libs
        data = dict(name="CreateTestLibrary")
        create_response = self._post("libraries", data=data, admin=False, anon=True)
        self._assert_status_code_is(create_response, 403)
        # Anons can't delete libs
        library = self.library_populator.new_library("AnonDeleteTestLibrary")
        create_response = self._delete("libraries/%s" % library["id"], admin=False, anon=True)
        self._assert_status_code_is(create_response, 403)
        # Anons can't update libs
        data = dict(name="ChangedName", description="ChangedDescription", synopsis='ChangedSynopsis')
        create_response = self._patch("libraries/%s" % library["id"], data=data, admin=False, anon=True)
        self._assert_status_code_is(create_response, 403)

    def test_update(self):
        library = self.library_populator.new_library("UpdateTestLibrary")
        data = dict(name='ChangedName', description='ChangedDescription', synopsis='ChangedSynopsis')
        create_response = self._patch("libraries/%s" % library["id"], data=data, admin=True)
        self._assert_status_code_is(create_response, 200)
        library = create_response.json()
        self._assert_has_keys(library, 'name', 'description', 'synopsis')
        assert library['name'] == 'ChangedName'
        assert library['description'] == 'ChangedDescription'
        assert library['synopsis'] == 'ChangedSynopsis'

    def test_create_private_library_permissions(self):
        library = self.library_populator.new_library("PermissionTestLibrary")
        library_id = library["id"]
        role_id = self.library_populator.user_private_role_id()
        self.library_populator.set_permissions(library_id, role_id)
        create_response = self._create_folder(library)
        self._assert_status_code_is(create_response, 200)

    def test_create_dataset_denied(self):
        library = self.library_populator.new_private_library("ForCreateDatasets")
        folder_response = self._create_folder(library)
        self._assert_status_code_is(folder_response, 200)
        folder_id = folder_response.json()[0]['id']
        history_id = self.dataset_populator.new_history()
        hda_id = self.dataset_populator.new_dataset(history_id, content="1 2 3")['id']
        with self._different_user():
            payload = {'from_hda_id': hda_id}
            create_response = self._post("folders/%s/contents" % folder_id, payload)
            self._assert_status_code_is(create_response, 403)

    def test_create_dataset(self):
        library = self.library_populator.new_private_library("ForCreateDatasets")
        payload, files = self.library_populator.create_dataset_request(library, file_type="txt", contents="create_test")
        create_response = self._post("libraries/%s/contents" % library["id"], payload, files=files)
        self._assert_status_code_is(create_response, 200)
        library_datasets = create_response.json()
        assert len(library_datasets) == 1
        library_dataset = library_datasets[0]

        def show():
            return self._get("libraries/%s/contents/%s" % (library["id"], library_dataset["id"]))

        wait_on_state(show, assert_ok=True)
        library_dataset = show().json()
        self._assert_has_keys(library_dataset, "peek", "data_type")
        assert library_dataset["peek"].find("create_test") >= 0
        assert library_dataset["file_ext"] == "txt", library_dataset["file_ext"]

    def test_create_dataset_in_folder(self):
        library = self.library_populator.new_private_library("ForCreateDatasets")
        folder_response = self._create_folder(library)
        self._assert_status_code_is(folder_response, 200)
        folder_id = folder_response.json()[0]['id']
        history_id = self.dataset_populator.new_history()
        hda_id = self.dataset_populator.new_dataset(history_id, content="1 2 3")['id']
        payload = {'from_hda_id': hda_id}
        create_response = self._post("folders/%s/contents" % folder_id, payload)
        self._assert_status_code_is(create_response, 200)
        self._assert_has_keys(create_response.json(), "name", "id")

    def test_update_dataset_in_folder(self):
        library = self.library_populator.new_private_library("ForUpdateDataset")
        folder_response = self._create_folder(library)
        self._assert_status_code_is(folder_response, 200)
        folder_id = folder_response.json()[0]['id']
        history_id = self.dataset_populator.new_history()
        hda_id = self.dataset_populator.new_dataset(history_id, content="1 2 3")['id']
        payload = {'from_hda_id': hda_id, 'create_type': 'file', 'folder_id': folder_id}
        ld = self._post("libraries/%s/contents" % folder_id, payload)
        data = {'name': 'updated_name', 'file_ext': 'fastq', 'misc_info': 'updated_info', 'genome_build': 'updated_genome_build'}
        create_response = self._patch("libraries/datasets/%s" % ld.json()["id"], data=data)
        self._assert_status_code_is(create_response, 200)
        self._assert_has_keys(create_response.json(), "name", "file_ext", "misc_info", "genome_build")

    def test_invalid_update_dataset_in_folder(self):
        library = self.library_populator.new_private_library("ForInvalidUpdateDataset")
        folder_response = self._create_folder(library)
        self._assert_status_code_is(folder_response, 200)
        folder_id = folder_response.json()[0]['id']
        history_id = self.dataset_populator.new_history()
        hda_id = self.dataset_populator.new_dataset(history_id, content="1 2 3")['id']
        payload = {'from_hda_id': hda_id, 'create_type': 'file', 'folder_id': folder_id}
        ld = self._post("libraries/%s/contents" % folder_id, payload)
        data = {'file_ext': 'nonexisting_type'}
        create_response = self._patch("libraries/datasets/%s" % ld.json()["id"], data=data)
        self._assert_status_code_is(create_response, 400)
        assert 'This Galaxy does not recognize the datatype of:' in create_response.json()['err_msg']

    def test_create_datasets_in_library_from_collection(self):
        library = self.library_populator.new_private_library("ForCreateDatasetsFromCollection")
        folder_response = self._create_folder(library)
        self._assert_status_code_is(folder_response, 200)
        folder_id = folder_response.json()[0]['id']
        history_id = self.dataset_populator.new_history()
        hdca_id = self.dataset_collection_populator.create_list_in_history(history_id, contents=["xxx", "yyy"]).json()["id"]
        payload = {'from_hdca_id': hdca_id, 'create_type': 'file', 'folder_id': folder_id}
        create_response = self._post("libraries/%s/contents" % library['id'], payload)
        self._assert_status_code_is(create_response, 200)

    def test_create_datasets_in_folder_from_collection(self):
        library = self.library_populator.new_private_library("ForCreateDatasetsFromCollection")
        history_id = self.dataset_populator.new_history()
        hdca_id = self.dataset_collection_populator.create_list_in_history(history_id, contents=["xxx", "yyy"]).json()["id"]
        folder_response = self._create_folder(library)
        self._assert_status_code_is(folder_response, 200)
        folder_id = folder_response.json()[0]['id']
        payload = {'from_hdca_id': hdca_id}
        create_response = self._post("folders/%s/contents" % folder_id, payload)
        self._assert_status_code_is(create_response, 200)
        assert len(create_response.json()) == 2
        # Also test that anything different from a flat dataset collection list
        # is refused
        hdca_pair_id = self.dataset_collection_populator.create_list_of_pairs_in_history(history_id).json()['id']
        payload = {'from_hdca_id': hdca_pair_id}
        create_response = self._post("folders/%s/contents" % folder_id, payload)
        self._assert_status_code_is(create_response, 501)
        assert create_response.json()['err_msg'] == 'Cannot add nested collections to library. Please flatten your collection first.'

    def _create_folder(self, library):
        create_data = dict(
            folder_id=library["root_folder_id"],
            create_type="folder",
            name="New Folder",
        )
        return self._post("libraries/%s/contents" % library["id"], data=create_data)
