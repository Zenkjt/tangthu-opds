package main

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"testing"
)

func TestWriteCatalogBranchShardsAndPages(t *testing.T) {
	out := t.TempDir()
	files := make([]FileEntry, 0, 1003)
	files = append(files, FileEntry{ID: "folder-A", ParentID: "root-A", Name: "Subfolder", IsFolder: true})
	for i := 0; i < 1001; i++ {
		files = append(files, FileEntry{ID: fmtID(i), ParentID: "root-A", Name: "Book", MIME: "application/epub+zip"})
	}
	files = append(files, FileEntry{ID: "nested-book", ParentID: "folder-A", Name: "Nested.epub"})
	branch := Branch{Config: BranchConfig{ID: "shelf-A", DisplayName: "Shelf A", RootFolderID: "root-A"}, DriveFolderName: "Drive A", Files: files}

	if err := writeCatalogBranchShards(out, branch); err != nil {
		t.Fatal(err)
	}
	rootPath := filepath.Join(out, "catalog", "shelf-A", "root.json")
	data, err := os.ReadFile(rootPath)
	if err != nil {
		t.Fatal(err)
	}
	var root struct {
		BranchID    string             `json:"branch_id"`
		RootShards  []string           `json:"root_shards"`
		Directories []catalogDirectory `json:"directories"`
	}
	if err := json.Unmarshal(data, &root); err != nil {
		t.Fatal(err)
	}
	if root.BranchID != "shelf-A" {
		t.Fatalf("branch id = %q", root.BranchID)
	}
	if len(root.RootShards) != 2 {
		t.Fatalf("expected 2 root pages, got %d", len(root.RootShards))
	}
	if len(root.Directories) != 1 || len(root.Directories[0].Shards) != 1 {
		t.Fatalf("unexpected directory index: %#v", root.Directories)
	}

	nestedPath := filepath.Join(out, filepath.FromSlash(root.Directories[0].Shards[0]))
	nestedData, err := os.ReadFile(nestedPath)
	if err != nil {
		t.Fatal(err)
	}
	var nested struct {
		FolderID string        `json:"folder_id"`
		Items    []catalogFile `json:"items"`
	}
	if err := json.Unmarshal(nestedData, &nested); err != nil {
		t.Fatal(err)
	}
	if nested.FolderID != "folder-A" || len(nested.Items) != 1 || nested.Items[0].ID != "nested-book" {
		t.Fatalf("unexpected nested shard: %#v", nested)
	}
}

func TestMergeCatalogShardsPreservesOtherBranches(t *testing.T) {
	out := t.TempDir()
	first := Branch{Config: BranchConfig{ID: "A", DisplayName: "A", RootFolderID: "root-A"}, Files: []FileEntry{{ID: "a1", ParentID: "root-A", Name: "A.epub"}}}
	second := Branch{Config: BranchConfig{ID: "B", DisplayName: "B", RootFolderID: "root-B"}, Files: []FileEntry{{ID: "b1", ParentID: "root-B", Name: "B.epub"}}}
	if err := writeCatalogShards(out, []Branch{first, second}); err != nil {
		t.Fatal(err)
	}
	if err := writeCatalogManifest(out, []Branch{first, second}); err != nil {
		t.Fatal(err)
	}

	updated := Branch{Config: BranchConfig{ID: "A", DisplayName: "A renamed", RootFolderID: "root-A"}, Files: []FileEntry{{ID: "a2", ParentID: "root-A", Name: "New.epub"}}}
	if err := mergeCatalogShards(out, []Branch{updated}); err != nil {
		t.Fatal(err)
	}
	manifest, err := readCatalogManifest(filepath.Join(out, "catalog.json"))
	if err != nil {
		t.Fatal(err)
	}
	if len(manifest.Branches) != 2 {
		t.Fatalf("expected 2 branches, got %d", len(manifest.Branches))
	}
	if manifest.Branches[0].Name != "A renamed" || manifest.Branches[1].ID != "B" {
		t.Fatalf("unexpected merged manifest: %#v", manifest.Branches)
	}
}

func fmtID(i int) string { return fmt.Sprintf("book-%04d", i) }

func TestEmptyDirectoryShardListIsEmptyArray(t *testing.T) {
	out := t.TempDir()
	branch := Branch{
		Config: BranchConfig{ID: "shelf-empty", DisplayName: "Shelf", RootFolderID: "root"},
		Files:  []FileEntry{{ID: "empty-folder", ParentID: "root", Name: "Empty", IsFolder: true}},
	}
	if err := writeCatalogBranchShards(out, branch); err != nil {
		t.Fatal(err)
	}
	data, err := os.ReadFile(filepath.Join(out, "catalog", "shelf-empty", "root.json"))
	if err != nil {
		t.Fatal(err)
	}
	var root struct {
		Directories []struct {
			ID     string   `json:"id"`
			Shards []string `json:"shards"`
		} `json:"directories"`
	}
	if err := json.Unmarshal(data, &root); err != nil {
		t.Fatal(err)
	}
	if len(root.Directories) != 1 || root.Directories[0].ID != "empty-folder" {
		t.Fatalf("unexpected directory metadata: %#v", root.Directories)
	}
	if root.Directories[0].Shards == nil || len(root.Directories[0].Shards) != 0 {
		t.Fatalf("empty directory shards must be [], got %#v", root.Directories[0].Shards)
	}
}

func TestBranchLessPrioritizesVNThenAlphabetical(t *testing.T) {
	got := []string{"Sách Yến", "VN02", "ABC", "VN01"}
	for i := 0; i < len(got); i++ {
		for j := i + 1; j < len(got); j++ {
			if branchLess(got[j], got[i]) {
				got[i], got[j] = got[j], got[i]
			}
		}
	}
	want := []string{"VN01", "VN02", "ABC", "Sách Yến"}
	for i := range want {
		if got[i] != want[i] {
			t.Fatalf("sorted branches = %#v, want %#v", got, want)
		}
	}
}

func TestCatalogStatsExcludeFoldersAndSeparateFonts(t *testing.T) {
	files := []FileEntry{
		{ID: "folder", Name: "Books", IsFolder: true},
		{ID: "e1", Name: "Novel.EPUB"},
		{ID: "e2", Name: "scan.PDF"},
		{ID: "e3", Name: "archive.zip"},
		{ID: "f1", Name: "Reader.CPFONT"},
		{ID: "f2", Name: "typeface.TTF"},
		{ID: "f3", Name: "OpenType.OTF"},
		{ID: "x1", Name: "notes.exe"},
		{ID: "x2", Name: "no-extension"},
	}
	if got := countBooks(files); got != 3 {
		t.Fatalf("book count = %d, want 3", got)
	}
	if got := countFonts(files); got != 3 {
		t.Fatalf("font count = %d, want 3", got)
	}
	got := countBookFormats(files)
	if got["EPUB"] != 1 || got["PDF"] != 1 || got["ZIP"] != 1 || len(got) != 3 {
		t.Fatalf("format counts = %#v", got)
	}
}

func TestIncrementalMergePreservesStaticStatsOfOtherShelves(t *testing.T) {
	out := t.TempDir()
	first := Branch{Config: BranchConfig{ID: "A", DisplayName: "A", RootFolderID: "root-A"}, Files: []FileEntry{{ID: "a1", ParentID: "root-A", Name: "A.epub"}}}
	second := Branch{Config: BranchConfig{ID: "B", DisplayName: "B", RootFolderID: "root-B"}, Files: []FileEntry{
		{ID: "b1", ParentID: "root-B", Name: "B.pdf"},
		{ID: "b2", ParentID: "root-B", Name: "Font.ttf"},
	}}
	if err := writeCatalogShards(out, []Branch{first, second}); err != nil {
		t.Fatal(err)
	}
	if err := writeCatalogManifest(out, []Branch{first, second}); err != nil {
		t.Fatal(err)
	}
	updated := Branch{Config: BranchConfig{ID: "A", DisplayName: "A", RootFolderID: "root-A"}, Files: []FileEntry{
		{ID: "a2", ParentID: "root-A", Name: "A2.epub"},
		{ID: "a3", ParentID: "root-A", Name: "A3.mobi"},
	}}
	if err := mergeCatalogShards(out, []Branch{updated}); err != nil {
		t.Fatal(err)
	}
	manifest, err := readCatalogManifest(filepath.Join(out, "catalog.json"))
	if err != nil {
		t.Fatal(err)
	}
	if manifest.Branches[0].BookCount != 2 || manifest.Branches[0].FormatCounts["MOBI"] != 1 {
		t.Fatalf("updated shelf stats = %#v", manifest.Branches[0])
	}
	if manifest.Branches[1].BookCount != 1 || manifest.Branches[1].FontCount != 1 || manifest.Branches[1].FormatCounts["PDF"] != 1 {
		t.Fatalf("untouched shelf stats were not preserved: %#v", manifest.Branches[1])
	}
}

func TestSnapshotManifestAcceptsProgressiveGeneration(t *testing.T) {
	manifest := SnapshotManifest{
		Version: 2, Storage: "r2", BranchID: "A", GenerationID: "g1",
		Complete: false, PageCount: 0, Pages: []string{}, ItemCount: 0,
	}
	if !validSnapshotManifest(manifest, "A") {
		t.Fatal("partial generation should be accepted")
	}
	manifest.Complete = true
	if !validSnapshotManifest(manifest, "A") {
		t.Fatal("complete generation should also be accepted")
	}
	if validSnapshotManifest(manifest, "B") {
		t.Fatal("manifest for another shelf must be rejected")
	}
	manifest.PageCount = 1
	if validSnapshotManifest(manifest, "A") {
		t.Fatal("manifest with mismatched page count must be rejected")
	}
}

func TestCatalogSearchIndexContainsFilesAndFolderPaths(t *testing.T) {
	out := t.TempDir()
	branch := Branch{
		Config: BranchConfig{ID: "shelf-search", DisplayName: "Search Shelf", RootFolderID: "root"},
		Files: []FileEntry{
			{ID: "folder-a", ParentID: "root", Name: "Văn học", IsFolder: true},
			{ID: "book-a", ParentID: "folder-a", Name: "Đất rừng phương Nam.epub", MIME: "application/epub+zip", Size: 123},
			{ID: "book-b", ParentID: "root", Name: "Science.pdf", MIME: "application/pdf", Size: 456},
		},
	}
	if err := writeCatalogBranchShards(out, branch); err != nil {
		t.Fatal(err)
	}
	meta := branchCatalogMeta(branch)
	if len(meta.SearchShards) != 1 {
		t.Fatalf("search shards = %#v, want one shard", meta.SearchShards)
	}
	data, err := os.ReadFile(filepath.Join(out, filepath.FromSlash(meta.SearchShards[0])))
	if err != nil {
		t.Fatal(err)
	}
	var shard struct {
		BranchID string `json:"branch_id"`
		Items    []struct {
			ID   string `json:"id"`
			Path string `json:"path"`
		} `json:"items"`
	}
	if err := json.Unmarshal(data, &shard); err != nil {
		t.Fatal(err)
	}
	if shard.BranchID != "shelf-search" || len(shard.Items) != 2 {
		t.Fatalf("unexpected search shard: %#v", shard)
	}
	paths := map[string]string{}
	for _, item := range shard.Items {
		paths[item.ID] = item.Path
	}
	if paths["book-a"] != "/Văn học/" || paths["book-b"] != "/" {
		t.Fatalf("unexpected indexed paths: %#v", paths)
	}
}
