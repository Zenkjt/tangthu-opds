package metadata

import (
	"archive/zip"
	"bytes"
	"context"
	"encoding/binary"
	"encoding/xml"
	"html"
	"io"
	"net/url"
	"path"
	"regexp"
	"strings"
	"unicode"

	"github.com/Zenkjt/tangthu-opds/internal/drive"
)

type Metadata struct {
	Title       string   `json:"title,omitempty"`
	Authors     []string `json:"authors,omitempty"`
	Publisher   string   `json:"publisher,omitempty"`
	Date        string   `json:"date,omitempty"`
	Year        string   `json:"year,omitempty"`
	ISBN        string   `json:"isbn,omitempty"`
	Language    string   `json:"language,omitempty"`
	Series      string   `json:"series,omitempty"`
	Description string   `json:"description,omitempty"`
	Subjects    []string `json:"subjects,omitempty"`
	Cover       []byte   `json:"-"`
	CoverType   string   `json:"-"`
}

const maxRead = 25 * 1024 * 1024

func Extract(ctx context.Context, client *drive.Client, f drive.File) Metadata {
	ext := strings.ToLower(filepathExt(f.Name))
	if ext != ".epub" && ext != ".mobi" && ext != ".azw3" {
		return Metadata{}
	}
	resp, err := client.Open(ctx, f.ID, "")
	if err != nil {
		return Metadata{}
	}
	defer resp.Body.Close()
	data, err := io.ReadAll(io.LimitReader(resp.Body, maxRead+1))
	if err != nil || len(data) > maxRead {
		return Metadata{}
	}
	switch ext {
	case ".epub":
		return parseEPUB(data)
	case ".mobi", ".azw3":
		return parseMOBI(data)
	default:
		return Metadata{}
	}
}

func filepathExt(name string) string {
	i := strings.LastIndexByte(name, '.')
	if i < 0 {
		return ""
	}
	return name[i:]
}

type containerXML struct {
	Rootfile struct {
		FullPath string `xml:"full-path,attr"`
	} `xml:"rootfiles>rootfile"`
}

type opfMeta struct {
	Name     string `xml:"name,attr"`
	Property string `xml:"property,attr"`
	Content  string `xml:"content,attr"`
	Refines  string `xml:"refines,attr"`
	Value    string `xml:",chardata"`
}

type opfItem struct {
	ID         string `xml:"id,attr"`
	Href       string `xml:"href,attr"`
	MediaType  string `xml:"media-type,attr"`
	Properties string `xml:"properties,attr"`
}

type opfPackage struct {
	Metadata struct {
		Title       []string  `xml:"http://purl.org/dc/elements/1.1/ title"`
		Creator     []string  `xml:"http://purl.org/dc/elements/1.1/ creator"`
		Publisher   []string  `xml:"http://purl.org/dc/elements/1.1/ publisher"`
		Date        []string  `xml:"http://purl.org/dc/elements/1.1/ date"`
		Identifier  []string  `xml:"http://purl.org/dc/elements/1.1/ identifier"`
		Language    []string  `xml:"http://purl.org/dc/elements/1.1/ language"`
		Description []string  `xml:"http://purl.org/dc/elements/1.1/ description"`
		Subject     []string  `xml:"http://purl.org/dc/elements/1.1/ subject"`
		Meta        []opfMeta `xml:"meta"`
	} `xml:"metadata"`
	Manifest struct {
		Items []opfItem `xml:"item"`
	} `xml:"manifest"`
}

func parseEPUB(data []byte) Metadata {
	z, err := zip.NewReader(bytes.NewReader(data), int64(len(data)))
	if err != nil {
		return Metadata{}
	}
	files := map[string]*zip.File{}
	for _, f := range z.File {
		files[f.Name] = f
	}
	c := files["META-INF/container.xml"]
	if c == nil {
		return Metadata{}
	}
	cb, err := readZip(c)
	if err != nil {
		return Metadata{}
	}
	var cx containerXML
	if xml.Unmarshal(cb, &cx) != nil || cx.Rootfile.FullPath == "" {
		return Metadata{}
	}
	opf := files[cx.Rootfile.FullPath]
	if opf == nil {
		return Metadata{}
	}
	ob, err := readZip(opf)
	if err != nil {
		return Metadata{}
	}
	var p opfPackage
	if xml.Unmarshal(ob, &p) != nil {
		return Metadata{}
	}
	m := Metadata{}
	m.Title = first(p.Metadata.Title)
	m.Authors = cleanList(p.Metadata.Creator)
	m.Publisher = first(p.Metadata.Publisher)
	m.Date = first(p.Metadata.Date)
	m.Year = yearOf(m.Date)
	m.Language = first(p.Metadata.Language)
	m.Description = cleanDescription(first(p.Metadata.Description))
	m.Subjects = cleanList(p.Metadata.Subject)
	for _, id := range p.Metadata.Identifier {
		if looksISBN(id) {
			m.ISBN = normalizeISBN(id)
			break
		}
	}
	for _, x := range p.Metadata.Meta {
		prop := strings.ToLower(strings.TrimSpace(x.Property))
		name := strings.ToLower(strings.TrimSpace(x.Name))
		if prop == "belongs-to-collection" || name == "calibre:series" || name == "series" {
			if strings.TrimSpace(x.Value) != "" {
				m.Series = strings.TrimSpace(x.Value)
			}
		}
	}
	m.Cover, m.CoverType = extractEPUBCover(files, cx.Rootfile.FullPath, p)
	return m
}

// cleanDescription converts descriptions copied from EPUB HTML/XHTML into
// plain readable text. It deliberately does not preserve or execute markup.
func cleanDescription(s string) string {
	s = strings.TrimSpace(s)
	if s == "" {
		return ""
	}

	// EPUB metadata is sometimes HTML-escaped more than once
	// (for example &amp;lt;p&amp;gt;...&amp;lt;/p&amp;gt;).
	// Decode and strip markup repeatedly so no HTML tags survive.
	reBlock := regexp.MustCompile(`(?is)<\s*/?\s*(p|div|br|li|h[1-6]|blockquote|tr|pre)\b[^>]*>`)
	reTag := regexp.MustCompile(`(?is)<[^>]*>`)

	for i := 0; i < 3; i++ {
		decoded := html.UnescapeString(s)
		if decoded == s {
			break
		}
		s = decoded
	}

	for i := 0; i < 3; i++ {
		before := s
		s = reBlock.ReplaceAllString(s, "\n")
		s = reTag.ReplaceAllString(s, "")
		s = html.UnescapeString(s)
		if s == before {
			break
		}
	}

	// Normalize whitespace while retaining paragraph breaks.
	lines := strings.Split(s, "\n")
	out := make([]string, 0, len(lines))
	for _, line := range lines {
		line = strings.Map(func(r rune) rune {
			if unicode.IsSpace(r) {
				return ' '
			}
			return r
		}, line)
		line = strings.Join(strings.Fields(line), " ")
		if line != "" {
			out = append(out, line)
		}
	}

	return strings.TrimSpace(strings.Join(out, "\n\n"))
}

func extractEPUBCover(files map[string]*zip.File, opfPath string, p opfPackage) ([]byte, string) {
	var coverID string
	for _, x := range p.Metadata.Meta {
		if strings.EqualFold(strings.TrimSpace(x.Name), "cover") && strings.TrimSpace(x.Content) != "" {
			coverID = strings.TrimSpace(x.Content)
			break
		}
	}
	var item *opfItem
	for i := range p.Manifest.Items {
		it := &p.Manifest.Items[i]
		if coverID != "" && it.ID == coverID {
			item = it
			break
		}
	}
	if item == nil {
		for i := range p.Manifest.Items {
			it := &p.Manifest.Items[i]
			props := strings.Fields(strings.ToLower(it.Properties))
			for _, prop := range props {
				if prop == "cover-image" {
					item = it
					break
				}
			}
			if item != nil {
				break
			}
		}
	}
	if item == nil {
		for i := range p.Manifest.Items {
			it := &p.Manifest.Items[i]
			mt := strings.ToLower(it.MediaType)
			h := strings.ToLower(it.Href)
			if strings.HasPrefix(mt, "image/") && (strings.Contains(h, "cover") || strings.Contains(h, "jacket")) {
				item = it
				break
			}
		}
	}
	if item == nil {
		return nil, ""
	}
	name := resolveEPUBPath(opfPath, item.Href)
	zf := files[name]
	if zf == nil {
		return nil, ""
	}
	data, err := readZip(zf)
	if err != nil || len(data) == 0 || len(data) > 8*1024*1024 {
		return nil, ""
	}
	return data, coverType(item.MediaType, name)
}

func resolveEPUBPath(opfPath, href string) string {
	href = strings.SplitN(href, "#", 2)[0]
	if u, err := url.PathUnescape(href); err == nil {
		href = u
	}
	return path.Clean(path.Join(path.Dir(opfPath), href))
}

func coverType(mimeType, name string) string {
	mt := strings.ToLower(strings.TrimSpace(mimeType))
	switch mt {
	case "image/jpeg", "image/jpg":
		return "jpg"
	case "image/png":
		return "png"
	case "image/webp":
		return "webp"
	case "image/gif":
		return "gif"
	}
	ext := strings.ToLower(filepathExt(name))
	if ext == ".jpeg" {
		return "jpg"
	}
	if strings.HasPrefix(ext, ".") {
		return strings.TrimPrefix(ext, ".")
	}
	return "jpg"
}

func readZip(f *zip.File) ([]byte, error) {
	r, err := f.Open()
	if err != nil {
		return nil, err
	}
	defer r.Close()
	return io.ReadAll(io.LimitReader(r, maxRead+1))
}

func first(v []string) string {
	for _, s := range v {
		if strings.TrimSpace(s) != "" {
			return strings.TrimSpace(s)
		}
	}
	return ""
}

func cleanList(v []string) []string {
	var out []string
	seen := map[string]bool{}
	for _, s := range v {
		s = strings.TrimSpace(s)
		if s != "" && !seen[strings.ToLower(s)] {
			seen[strings.ToLower(s)] = true
			out = append(out, s)
		}
	}
	return out
}

func yearOf(s string) string {
	if m := regexp.MustCompile(`\b(1[5-9]\d{2}|20\d{2}|21\d{2})\b`).FindString(s); m != "" {
		return m
	}
	return ""
}

func looksISBN(s string) bool { n := normalizeISBN(s); return len(n) == 10 || len(n) == 13 }

func normalizeISBN(s string) string {
	var b strings.Builder
	for _, r := range s {
		if r >= '0' && r <= '9' {
			b.WriteRune(r)
		} else if r == 'X' || r == 'x' {
			b.WriteRune('X')
		}
	}
	return b.String()
}

func parseMOBI(data []byte) Metadata {
	m := Metadata{}
	if len(data) < 78 {
		return m
	}
	records := int(binary.BigEndian.Uint16(data[76:78]))
	if records < 1 || len(data) < 86 {
		return m
	}
	firstOffset := int(binary.BigEndian.Uint32(data[78:82]))
	if firstOffset < 0 || firstOffset >= len(data) {
		return m
	}
	end := len(data)
	if records > 1 && len(data) >= 94 {
		next := int(binary.BigEndian.Uint32(data[86:90]))
		if next > firstOffset && next < end {
			end = next
		}
	}
	rec := data[firstOffset:end]
	if len(rec) < 16 {
		return m
	}
	mobi := bytes.Index(rec, []byte("MOBI"))
	if mobi < 0 || len(rec) < mobi+132 {
		return m
	}
	headerLen := int(binary.BigEndian.Uint32(rec[mobi+4 : mobi+8]))
	if headerLen < 132 || mobi+headerLen > len(rec) {
		return m
	}
	exthFlags := binary.BigEndian.Uint32(rec[mobi+128 : mobi+132])
	if exthFlags&0x40 == 0 {
		return m
	}
	exth := mobi + headerLen
	if exth+12 > len(rec) || string(rec[exth:exth+4]) != "EXTH" {
		return m
	}
	count := int(binary.BigEndian.Uint32(rec[exth+8 : exth+12]))
	pos := exth + 12
	for i := 0; i < count && pos+8 <= len(rec); i++ {
		typ := binary.BigEndian.Uint32(rec[pos : pos+4])
		size := int(binary.BigEndian.Uint32(rec[pos+4 : pos+8]))
		if size < 8 || pos+size > len(rec) {
			break
		}
		val := strings.TrimSpace(string(rec[pos+8 : pos+size]))
		switch typ {
		case 100:
			m.Authors = splitAuthors(val)
		case 101:
			m.Publisher = val
		case 103:
			m.Description = cleanDescription(val)
		case 104:
			m.ISBN = normalizeISBN(val)
		case 105:
			m.Subjects = splitSubjects(val)
		case 106:
			m.Date = val
		case 503:
			m.Title = val
		case 524:
			m.Language = val
		case 501:
			if m.Series == "" {
				m.Series = val
			}
		}
		pos += size
	}
	m.Year = yearOf(m.Date)
	return m
}

func splitAuthors(s string) []string {
	s = strings.TrimSpace(s)
	if s == "" {
		return nil
	}
	return []string{s}
}

func splitSubjects(s string) []string {
	parts := strings.FieldsFunc(s, func(r rune) bool { return r == ';' || r == ',' })
	return cleanList(parts)
}
