package drive

import "testing"

func TestEscapeQuery(t *testing.T) {
	if got := escapeQuery("a'b"); got != `a\'b` {
		t.Fatalf("escapeQuery() = %q, want %q", got, `a\'b`)
	}
}

func TestIsFolder(t *testing.T) {
	if !IsFolder(File{MIMEType: folderMIME}) {
		t.Fatal("folder MIME should be recognized")
	}
	if IsFolder(File{MIMEType: "application/epub+zip"}) {
		t.Fatal("ebook MIME must not be recognized as folder")
	}
}
