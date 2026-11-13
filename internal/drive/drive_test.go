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
	for _, name := range []string{"comic.cbz", "legacy.lit", "help.chm", "reader.prc", "document.pdf", "archive.zip", "document.doc", "document.docx", "notes.txt", "readme.md"} {
		if !IsSupportedBook(File{Name: name, Size: 1024}) {
			t.Errorf("IsSupportedBook(%q) = false, want true", name)
		}
	}
}

func TestIsSupportedBookDoesNotApplyFileSizeLimit(t *testing.T) {
	const largeFileSize = 2 * 1024 * 1024 * 1024
	if !IsSupportedBook(File{Name: "large.epub", Size: largeFileSize}) {
		t.Fatal("large supported book should be included; scan does not download file contents")
	}
	if IsSupportedBook(File{Name: "negative.epub", Size: -1}) {
		t.Fatal("negative file size should remain invalid")
	}
}
