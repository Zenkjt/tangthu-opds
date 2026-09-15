package main

import "testing"

func TestExtractFolderID(t *testing.T) {
	tests := []struct{ in, want string }{
		{"ABC123", "ABC123"},
		{"https://drive.google.com/drive/folders/ABC123", "ABC123"},
		{"https://drive.google.com/drive/folders/ABC123?usp=sharing", "ABC123"},
		{"https://drive.google.com/drive/u/0/folders/ABC123", "ABC123"},
		{"", ""},
		{"https://example.com/not-a-drive-folder", ""},
	}
	for _, tt := range tests {
		if got := extractFolderID(tt.in); got != tt.want {
			t.Errorf("extractFolderID(%q) = %q, want %q", tt.in, got, tt.want)
		}
	}
}

func TestVNPriority(t *testing.T) {
	for _, name := range []string{"VN Y Khoa", "VN Văn học", "VN"} {
		if !vnPriority(name) {
			t.Errorf("vnPriority(%q) = false, want true", name)
		}
	}
	for _, name := range []string{"vn books", "Vietnam Books", "Vietnamese"} {
		if vnPriority(name) {
			t.Errorf("vnPriority(%q) = true, want false", name)
		}
	}
}

func TestChildrenFoldersFirst(t *testing.T) {
	br := Branch{Files: []FileEntry{
		{ID: "f", ParentID: "root", Name: "z.epub"},
		{ID: "d", ParentID: "root", Name: "Books", IsFolder: true},
		{ID: "x", ParentID: "other", Name: "ignored.epub"},
	}}
	rows := children(br, "root")
	if len(rows) != 2 || !rows[0].IsFolder || rows[0].Name != "Books" || rows[1].Name != "z.epub" {
		t.Fatalf("unexpected children order: %#v", rows)
	}
}

func TestFileInBranch(t *testing.T) {
	br := Branch{Files: []FileEntry{{ID: "book", Name: "book.epub"}, {ID: "folder", Name: "Folder", IsFolder: true}}}
	if _, ok := fileIn(br, "folder"); ok {
		t.Fatal("folder must not be acquirable")
	}
	if f, ok := fileIn(br, "book"); !ok || f.Name != "book.epub" {
		t.Fatal("book should be acquirable")
	}
}
