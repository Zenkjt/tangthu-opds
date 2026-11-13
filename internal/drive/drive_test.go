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

func TestIsSupportedBookRecognizesAdditionalFormats(t *testing.T) {
	for _, name := range []string{"comic.cbz", "legacy.lit", "help.chm", "reader.prc", "document.pdf", "archive.zip"} {
		if !IsSupportedBook(File{Name: name, Size: 1024}) {
			t.Errorf("IsSupportedBook(%q) = false, want true", name)
		}
	}
}

func TestIsSupportedBookKeepsSizeLimit(t *testing.T) {
	if IsSupportedBook(File{Name: "archive.zip", Size: maxBookSize + 1}) {
		t.Fatal("oversized ZIP should remain excluded by the 25 MiB limit")
	}
}
