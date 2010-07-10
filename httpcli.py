import ioloop
import iostream
import socket
import time
import sys
import string, random

# HTTP verbs
HTTP_GET        = 'GET'
HTTP_POST       = 'POST'
HTTP_HEAD       = 'HEAD'
HTTP_PUT        = 'PUT'
HTTP_DELETE     = 'DELETE'
HTTP_OPTIONS    = 'OPTIONS'
HTTP_TRACE      = 'TRACE'

########################################################################
def gen_rotate(lst):
    count = len(lst)
    index = 0
    
    while True:
        yield lst[index]
        index += 1
        if index >= count:
            index = 0

def _rand_data(sample, sample_len):
    result = ''
    for i in random.sample(sample, sample_len):
        result+=i
    return result

class HttpRequestBuilder(object):
    def __init__(self, host, req_type_gen, doc_uri_gen, ua_gen, referer_gen, 
                 num_requests=100, keep_alive=False, gzip=False, cookie_len=32, 
                 post_data_len=0, finish_request=False):
        self._host = host
        self._req_type_gen = req_type_gen
        self._doc_uri_gen = doc_uri_gen
        self._uagenerator = ua_gen
        self._keepalive = keep_alive
        self._gzip = gzip
        self._referer_gen = referer_gen
        self._cookie_len = cookie_len
        self._post_data_len = post_data_len
        self._num_requests = num_requests
        self._finish_request = finish_request
        
        self._requests_cache = list()
        for i in xrange(self._num_requests):
            self._requests_cache.append(self._build_request())
        self._cur_index = 0        
    
    #----------------------------------------------------------------------
    def _build_request(self):
        req_type = self._req_type_gen.next()
        request = '%s %s HTTP/1.1\r\nHost: %s\r\nUser-Agent: %s\r\nAccept: */*' % (req_type, 
                                                                                   self._doc_uri_gen.next(), 
                                                                                   self._host, 
                                                                                   self._uagenerator.next())
        
        if self._keepalive:
            request += '\r\nKeep-Alive: 300\r\nConnection: Keep-Alive'
        
        if self._gzip:
            request += '\r\nAccept-Encoding: gzip'

        if self._referer_gen is not None:
            request += '\r\nReferer: %s' % (self._referer_gen.next())
            
        rand_data = string.letters + string.digits
        chunk_size = len(rand_data)
        
        if self._cookie_len > 0:
            request += '\r\nCookie: '            
            
            if self._cookie_len > chunk_size:
                chunk = int(self._cookie_len / chunk_size)
                for i in xrange(chunk):
                    request += ('data%i=%s; ' % (i, _rand_data(rand_data, chunk_size)))
                request += ('data=%s;' % (_rand_data(rand_data, chunk_size)))
            else:
                request += 'data=' + _rand_data(rand_data, self._cookie_len)

        if (self._post_data_len > 0) & (req_type == 'POST'):
            filler_len = random.randint(4, chunk_size)
            chunks = (self._post_data_len / filler_len) + 1
            
            filler_data = ''
            for i in random.sample(rand_data, filler_len):
                filler_data+=i
            
            request += '\r\nContent-Type: application/x-www-form-urlencoded\r\nContent-Length: %i\r\n\r\n' % (chunks * filler_len)            
            request += (filler_data * chunks)
        elif self._finish_request:
            request += '\r\n\r\n'
        
        return request
    
    #----------------------------------------------------------------------
    def next_request(self):
        result = self._requests_cache[self._cur_index]
        self._cur_index += 1
        if self._cur_index >= self._num_requests:
            self._cur_index = 0
        return result


class HttpBot(object):
    #----------------------------------------------------------------------
    def __init__(self, host_addr, bot_master, send_data, send_size=2, send_interval=0.5, graceful_close=False):
        self._send_data = send_data
        self._send_size = send_size
        self._data_offset = 0
        self._chunk_size = 0
        self._data_size = len(send_data)
        self._send_interval = send_interval
        self._graceful_close = graceful_close
        self._bot_master = bot_master
        
        self._fd = socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0)
        try:
            self._fd.connect(host_addr)
        except:
            self._fd.close()
            raise
        
        self._stream = iostream.IOStream(self._fd)
        ioloop.IOLoop.instance().add_timeout(time.time() + self._send_interval, self._on_send_complete)
    
    #----------------------------------------------------------------------
    def _on_send_data(self):
        self._chunk_size = self._send_size if (self._data_offset + self._send_size < self._data_size) else (self._data_size - self._data_offset)
        try:
            self._stream.write(self._send_data[self._data_offset:self._data_offset + self._chunk_size], self._on_send_complete)        
        except IOError, e:
            print "remote connection reset!"
            self._die()
    
    
    #----------------------------------------------------------------------
    def _on_send_complete(self):
        self._data_offset += self._chunk_size

        print ">> %i of %i sent" % ( self._data_offset, self._data_size)
        
        if self._data_offset < self._data_size:
            ioloop.IOLoop.instance().add_timeout(time.time() + self._send_interval, self._on_send_data)
        elif self._graceful_close:
            self._stream.read_until("\r\n\r\n", self._on_read_headers)
        else:
            self._die()
            
    #----------------------------------------------------------------------
    def _get_content_length(self, headers_string):
        headers_string = headers_string[headers_string.find("\r\n"):]
        for line in headers_string.splitlines():
            if line:
                name, value = line.split(":", 1)
                
                if (name.upper() == 'CONTENT-LENGTH'):
                    return int(value)
        return 0

    #----------------------------------------------------------------------
    def _on_read_headers(self, data):
        print "<< %i header" % (len(data))
        num_bytes = self._get_content_length(data)
        if num_bytes > 0:
            self._stream.read_bytes(num_bytes, self._on_read_body)
        else:
            self._die()
    
    #----------------------------------------------------------------------
    def _on_read_body(self, data):
        print r"<< %i body" % (len(data))
        self._die()
    
    #----------------------------------------------------------------------
    def _die(self):
        #self._bot_master.on_die(self)
        self._stream.close()
        self._stream = None


req_type_gen = gen_rotate([HTTP_POST, HTTP_POST])
doc_uri_gen = gen_rotate(['/index.html', '/'])
ua_gen = referer_gen = gen_rotate(['a', 'b', 'c', 'd', 'e'])
rb = HttpRequestBuilder('local', req_type_gen, doc_uri_gen, ua_gen, referer_gen, 5, post_data_len=120, finish_request=True)

res = socket.getaddrinfo('localhost', 80, socket.AF_INET, socket.SOCK_STREAM, socket.SOL_TCP)[0]
af, socktype, proto, canonname, sa = res
#c1 = LorisHttpConnection(sa, None, rb.next_request(), send_size=70)
c1 = HttpBot(sa, None, rb.next_request(), graceful_close=0, send_size=4, send_interval=5)
c1 = HttpBot(sa, None, rb.next_request(), graceful_close=True, send_size=40, send_interval=1)
c1 = HttpBot(sa, None, rb.next_request(), graceful_close=True, send_size=20, send_interval=2)
try:
    ioloop.IOLoop.instance().start()    
except:
    ioloop.IOLoop.instance().stop()