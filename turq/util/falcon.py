# pylint: disable=unused-argument

class DisableCache:

    def process_response(self, req, resp, resource, req_succeeded):
        resp.cache_control = ['no-store']
