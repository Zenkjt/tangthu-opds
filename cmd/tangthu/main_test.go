package main

import "testing"

func TestExtractFolderID(t *testing.T) {
	tests := []struct {
		in, want string
	}{
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
