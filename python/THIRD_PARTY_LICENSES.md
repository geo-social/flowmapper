# Third-party components

`flowmapper.org` is MIT-licensed (see `LICENSE`). It ships or ports the following third-party
components, which keep their own licenses.

## Shipped files

| File | Component | License |
|---|---|---|
| `src/flowmapper_org/interactive/_static/ol.js`, `ol.css` | [OpenLayers](https://openlayers.org/) 6.3.1, © OpenLayers Contributors | BSD 2-Clause |
| `src/flowmapper_org/interactive/_static/proj4.js` | [proj4js](https://github.com/proj4js/proj4js), © 2014 Mike Bostock and proj4js contributors | MIT |
| `src/flowmapper_org/interactive/_static/d3.js` | [d3](https://d3js.org/) 6.2.0, © 2010–2020 Mike Bostock | ISC |
| `src/flowmapper_org/_data/colorbrewer.json` | [ColorBrewer](https://colorbrewer2.org/) colour schemes, © 2002 Cynthia Brewer, Mark Harrower and The Pennsylvania State University | Apache 2.0 |
| `src/flowmapper_org/_data/d3colors.json` | CSS named colours and Tableau 10 as defined in d3 (d3-color, d3-scale-chromatic) | ISC |
| `src/flowmapper_org/_data/us-states.json` | U.S. state boundaries as shipped with FlowMapper.org (derived from U.S. Census Bureau data) | Public domain (U.S. Government work) |

## Ported code (Python translations)

| Module | Ported from | License |
|---|---|---|
| `community/delaunay.py` | [Delaunator](https://github.com/mapbox/delaunator) (© 2017 Mapbox), [d3-delaunay](https://github.com/d3/d3-delaunay) (© 2018 Observable, Inc.) and d3-voronoi as bundled in d3 6.2.0 | ISC |
| `community/topojson.py` | [topojson](https://github.com/topojson/topojson) 1.6.19 (feature, merge), © 2012–2016 Michael Bostock | BSD 3-Clause |
| `classify.py`, `colors.py` (scale, quantile, bisect and interpolation helpers) | d3-array, d3-scale, d3-interpolate, d3-color (d3 6.2.0) | ISC |

## License texts

### BSD 2-Clause (OpenLayers)

Copyright 2005-present, OpenLayers Contributors. All rights reserved.

Redistribution and use in source and binary forms, with or without modification, are permitted
provided that the following conditions are met:

1. Redistributions of source code must retain the above copyright notice, this list of conditions
   and the following disclaimer.
2. Redistributions in binary form must reproduce the above copyright notice, this list of
   conditions and the following disclaimer in the documentation and/or other materials provided
   with the distribution.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND ANY EXPRESS OR
IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND
FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR
CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER
IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT
OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

### BSD 3-Clause (topojson)

Copyright (c) 2012-2016, Michael Bostock. All rights reserved.

Redistribution and use in source and binary forms, with or without modification, are permitted
provided that the following conditions are met:

* Redistributions of source code must retain the above copyright notice, this list of conditions
  and the following disclaimer.
* Redistributions in binary form must reproduce the above copyright notice, this list of
  conditions and the following disclaimer in the documentation and/or other materials provided
  with the distribution.
* The name Michael Bostock may not be used to endorse or promote products derived from this
  software without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND ANY EXPRESS OR
IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND
FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL MICHAEL BOSTOCK BE LIABLE FOR
ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

### ISC (d3, d3-delaunay, Delaunator)

Copyright 2010-2020 Mike Bostock; Copyright 2018 Observable, Inc.; Copyright 2017 Mapbox, Inc.

Permission to use, copy, modify, and/or distribute this software for any purpose with or without
fee is hereby granted, provided that the above copyright notice and this permission notice appear
in all copies.

THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES WITH REGARD TO THIS
SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE
AUTHOR BE LIABLE FOR ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES
WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN ACTION OF CONTRACT,
NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF OR IN CONNECTION WITH THE USE OR PERFORMANCE OF
THIS SOFTWARE.

### MIT (proj4js)

Copyright (c) 2014, Mike Bostock and proj4js contributors.

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and
associated documentation files (the "Software"), to deal in the Software without restriction,
including without limitation the rights to use, copy, modify, merge, publish, distribute,
sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or
substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT
NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM,
DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT
OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

### Apache License 2.0 (ColorBrewer)

Licensed under the Apache License, Version 2.0 (the "License"); you may not use this file except
in compliance with the License. You may obtain a copy of the License at
<http://www.apache.org/licenses/LICENSE-2.0>. Unless required by applicable law or agreed to in
writing, software distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the specific
language governing permissions and limitations under the License.

This product includes color specifications and designs developed by Cynthia Brewer
(<http://colorbrewer.org/>).
