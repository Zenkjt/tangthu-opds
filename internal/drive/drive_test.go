package drive

import "testing"

func TestEscapeQuery(t *testing.T) {
	if got := escapeQuery("a'b"); got != `a\'b` {
		t.Fatalf("escapeQuery() = %q, want %q", got, `a\'b`)
	}
}
