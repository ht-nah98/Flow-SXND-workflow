from agent.utils.paths import project_folder


def test_same_name_projects_get_separate_folders():
    a = project_folder({"id": "80f9f70f-dbfd", "name": "Bán Hàng, viên nén xơ dừa"})
    b = project_folder({"id": "4217d08b-477f", "name": "Bán Hàng, viên nén xơ dừa"})
    assert a == "ban_hang_vien_nen_xo_dua_80f9f70f" and a != b


def test_long_names_are_cut_and_objects_work():
    class P:
        id, name = "12345678-x", "x" * 100
    assert project_folder(P()) == "x" * 40 + "_12345678"
