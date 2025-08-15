package main

import (
	"context"
	"encoding/json"
	"flag"
	"fmt"
	"math"
	"reflect"
	"sync/atomic"
	"time"

	"github.com/apache/beam/sdks/v2/go/pkg/beam"
	"github.com/apache/beam/sdks/v2/go/pkg/beam/core/graph/window"
	"github.com/apache/beam/sdks/v2/go/pkg/beam/io/xlang/kafkaio"
	"github.com/apache/beam/sdks/v2/go/pkg/beam/log"
	"github.com/apache/beam/sdks/v2/go/pkg/beam/x/beamx"
)

type Msg struct {
	First  string  `json:"first_name"`
	Last   string  `json:"last_name"`
	Order  string  `json:"order_no"`
	Amount float64 `json:"amount"`
	TS     string  `json:"ts"`
	Seq    int     `json:"seq"`
}

var (
	expansionAddr    = flag.String("expansion_addr", "localhost:8097", "Kafka expansion service address")
	bootstrapServers = flag.String("bootstrap_servers", "", "Kafka bootstrap servers")
	topic            = flag.String("topic", "trellis-demo", "Kafka topic to read from")
	windowN          = flag.Int("roll_n", 50, "rolling average over the last N messages")
)

func init() {
	beam.RegisterType(reflect.TypeOf((*parseJSONFn)(nil)).Elem())
	beam.RegisterType(reflect.TypeOf((*sumAndAvgFn)(nil)).Elem())
}

func main() {
	flag.Parse()
	beam.Init()

	ctx := context.Background()
	p := beam.NewPipeline()
	s := p.Root()

	// Read from Kafka
	read := kafkaio.Read(s, *expansionAddr, *bootstrapServers, []string{*topic})
	vals := beam.DropKey(s, read)

	// Optional: windowing if needed
	windowed := beam.WindowInto(s, window.NewFixedWindows(15*time.Second), vals)

	// Parse JSON
	parsed := beam.ParDo(s, &parseJSONFn{}, windowed)

	// Compute cumulative sum and rolling average
	stats := beam.ParDo(s, &sumAndAvgFn{N: *windowN}, parsed)

	// Log results
	beam.ParDo0(s, func(line string) { log.Infof(ctx, line) }, stats)

	if err := beamx.Run(ctx, p); err != nil {
		log.Fatalf(ctx, "Pipeline failed: %v", err)
	}
}

type parseJSONFn struct{}

func (parseJSONFn) ProcessElement(b []byte, emit func(Msg)) error {
	var m Msg
	if err := json.Unmarshal(b, &m); err != nil {
		return nil
	}
	emit(m)
	return nil
}

type sumAndAvgFn struct {
	N int
}

func (f *sumAndAvgFn) Setup() {
	if f.N <= 0 {
		f.N = 50
	}
}

func (f *sumAndAvgFn) ProcessElement(ctx context.Context, m Msg, emit func(string)) {
	addSample(m.Amount, f.N)
	sum, count, avg := current()
	if count%int64(f.N) == 0 {
		line := fmt.Sprintf("seq=%d amount=%.2f running_sum=%.2f count=%d rolling_avg[%d]=%.2f",
			m.Seq, m.Amount, sum, count, f.N, avg)
		emit(line)
	}
}

// --- Rolling buffer logic ---
var runningSum uint64
var totalCount int64
var ring = struct {
	buf  [2048]float64
	size int
	pos  int
}{size: 0, pos: 0}

func addSample(v float64, n int) {
	for {
		old := atomic.LoadUint64(&runningSum)
		newf := math.Float64frombits(old) + v
		if atomic.CompareAndSwapUint64(&runningSum, old, math.Float64bits(newf)) {
			break
		}
	}
	atomic.AddInt64(&totalCount, 1)

	if n > len(ring.buf) {
		n = len(ring.buf)
	}
	if ring.size < n {
		ring.buf[ring.size] = v
		ring.size++
		return
	}
	ring.buf[ring.pos] = v
	ring.pos = (ring.pos + 1) % n
}

func current() (sum float64, count int64, rollingAvg float64) {
	sum = math.Float64frombits(atomic.LoadUint64(&runningSum))
	count = atomic.LoadInt64(&totalCount)
	n := ring.size
	if n == 0 {
		return sum, count, 0
	}
	var s float64
	for i := 0; i < n; i++ {
		s += ring.buf[i]
	}
	rollingAvg = s / float64(n)
	return
}
