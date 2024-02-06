from yaml.reader import *
from yaml.scanner import *
from yaml.parser import *
from yaml.constructor import *
from yaml.resolver import *
from yaml.events import *
from yaml.tokens import *
from yaml.composer import ComposerError

from discopy.frobenius import Hypergraph as H, Id, Ob, Ty, Box, Spider

class HypergraphComposer:

    def __init__(self):
        self.anchors = {}

    def check_node(self):
        # Drop the STREAM-START event.
        if self.check_event(StreamStartEvent):
            self.get_event()

        # If there are more documents available?
        return not self.check_event(StreamEndEvent)

    def get_node(self):
        # Get the root node of the next document.
        if not self.check_event(StreamEndEvent):
            return self.compose_document()

    def get_single_node(self):
        # Drop the STREAM-START event.
        self.get_event()

        # Compose a document if the stream is not empty.
        document = None
        if not self.check_event(StreamEndEvent):
            document = self.compose_document()

        # Ensure that the stream contains no more documents.
        if not self.check_event(StreamEndEvent):
            event = self.get_event()
            raise ComposerError("expected a single document in the stream",
                    document.start_mark, "but found another document",
                    event.start_mark)

        # Drop the STREAM-END event.
        self.get_event()

        return document

    def compose_document(self):
        # Drop the DOCUMENT-START event.
        self.get_event()

        # Compose the root node.
        tag = self.peek_event().tag
        node = self.compose_node(tag, None)

        # Drop the DOCUMENT-END event.
        self.get_event()

        self.anchors = {}
        return node

    def compose_node(self, parent, index):
        if self.check_event(AliasEvent):
            event = self.get_event()
            anchor = event.anchor
            if anchor not in self.anchors:
                raise ComposerError(None, None, "found undefined alias %r"
                        % anchor, event.start_mark)
            return self.anchors[anchor]
        event = self.peek_event()
        anchor = event.anchor
        if anchor is not None:
            if anchor in self.anchors:
                raise ComposerError("found duplicate anchor %r; first occurrence"
                        % anchor, self.anchors[anchor].start_mark,
                        "second occurrence", event.start_mark)
        self.descend_resolver(parent, index)
        if self.check_event(ScalarEvent):
            node = self.compose_scalar_node(parent, anchor)
        elif self.check_event(SequenceStartEvent):
            node = self.compose_sequence_node(parent, anchor)
        elif self.check_event(MappingStartEvent):
            node = self.compose_mapping_node(parent, anchor)
        self.ascend_resolver()
        return node

    def compose_scalar_node(self, parent, anchor):
        event = self.get_event()
        tag = event.tag
        if tag is None:
            tag = ""
        tag = tag.lstrip("!")
        if parent is None:
            parent = ""
        parent = parent.lstrip("!")
        # node = H(
        #     dom=Ty(str(event.value)), cod=Ty(str(event.value)),
        #     boxes=(),
        #     wires=(
        #         (
        #             Ob(str(event.value)),
        #         ), (), (
        #             Ob(str(event.value)),
        #         ),
        #     ),
        #     spider_types={Ob(str(event.value)): Ty(str(event.value))},
        # ) \
        # node = H.spiders(1, 1, Ty(str(event.value))) \
        # node = H.id(Ty(str(event.value))) \
        # node = H.from_box(Box(str(event.value), Ty(str(event.value)), Ty(str(event.value)))) \
        parent = parent or ""
        if event.value == "":
            node = H.id() if tag == "" else H.id(Ty(tag))
        else:
            node = H.from_box(Box(str(event.value), Ty(parent), Ty(tag))) \
        # node.to_diagram().draw()
        if anchor is not None:
            self.anchors[anchor] = node
        return node

    def compose_sequence_node(self, parent, anchor):
        start_event = self.get_event()
        tag = start_event.tag
        if tag is None or tag == '!':
            tag = self.DEFAULT_SEQUENCE_TAG
        node = H.id()
        # node = SequenceNode(tag, [],
        #         start_event.start_mark, None,
        #         flow_style=start_event.flow_style)
        if anchor is not None:
            self.anchors[anchor] = node
        index = 0
        while not self.check_event(SequenceEndEvent):
            item = self.compose_node(parent, index)
            node = compose_entry(node, item)
            index += 1
        end_event = self.get_event()
        node.end_mark = end_event.end_mark
        return node


    def compose_mapping_node(self, parent, anchor):
        start_event = self.get_event()
        tag = start_event.tag
        if tag is None:
            tag = ""
        tag = tag.lstrip("!")
        if parent is None:
            parent = ""
        parent = parent.lstrip("!")
        node = H.id()#Ty(str(start_event.start_mark)))
        if anchor is not None:
            self.anchors[anchor] = node
        keys, values = H.id(), H.id()
        while not self.check_event(MappingEndEvent):
            item_key = self.compose_node(tag, None)
            value_tag = self.peek_event().tag
            item_value = self.compose_node(tag, item_key)
            keys @= item_key
            values @= item_value
            kv = compose_entry(item_key, item_value)
            node @= kv
        end_event = self.get_event()
        node.end_mark = end_event.end_mark
        left = H.from_box(Box(tag, Ty(tag), keys.dom))
        mid = H.from_box(Box("", keys.cod, values.dom))
        right = H.from_box(Box(tag, values.cod, Ty(tag)))
        node = left >> keys >> mid >> values >> right
        # node = compose_entry(H.id(keys.dom), node)
        #     keys, H.id(values.dom))
        # node <<= values
        # node = compose_entry(
        #     H.spiders(1, 0, Ty(parent)) if parent else H.id(), node)
        return node

def compose_entry(k, v):
    # if v == H.id():
    #     return k
    spider_types = {
        Ob(s.name)
        for s in k.boxes + v.boxes}
    g = H(
        dom=k.cod, cod=v.dom,
        boxes=(),
        wires=(
            # tuple(Ob(s.name) for s in k.cod.inside), # input wires of the hypergraph
            k.cod.inside, # input wires of the hypergraph
            (),#tuple(((s,),(s,)) for s in spider_types),
            # tuple(Ob(s.name) for s in v.dom.inside), # input wires of the hypergraph
            v.dom.inside, # input wires of the hypergraph
        ),
        # spider_types=spider_types,
    )
    entry = k >> g >> v
    # print(entry.scalar_spiders)
    # g.to_diagram().draw()
    return entry


class HypergraphLoader(Reader, Scanner, Parser, HypergraphComposer, SafeConstructor, Resolver):

    def __init__(self, stream):
        Reader.__init__(self, stream)
        Scanner.__init__(self)
        Parser.__init__(self)
        HypergraphComposer.__init__(self)
        SafeConstructor.__init__(self)
        Resolver.__init__(self)
