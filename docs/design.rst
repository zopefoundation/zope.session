============================
 Sessions and Design Issues
============================

Sessions provide a way to temporarily associate information with a
client without requiring the authentication of a principal. We
associate an identifier with a particular client. Whenever we get a
request from that client, we compute the identifier and use the
identifier to look up associated information, which is stored on the
server.

A major disadvantage of sessions is that they require management of
information on the server. This can have major implications for
scalability. It is possible for a framework to make use of session
data very easy for the developer. This is great if scalability is not
an issue, otherwise, it is a booby trap.

Sessions introduce a number of issues to be considered.

Client Identification
=====================

Clients have to be identified. A number of approaches are possible,
including:

Using HTTP cookies
  The application assigns a client identifier,
  which is stored in a cookie. This technique is the most
  straightforward, but can be defeated if the client does not support
  HTTP cookies (usually because the feature has been disabled).

Using URLs.
  The application assigns a client identifier, which is
  stored in the URL. This makes URLs a bit uglier and requires some
  care. If people copy URLs and send them to others, then you could
  end up with multiple clients with the same session identifier. There
  are a number of ways to reduce the risk of accidental reuse of
  session identifiers:

    - Embed the client IP address in the identifier

    - Expire the identifier

Use hidden form variables.
  This complicates applications. It
  requires all requests to be POST requests and requires the
  maintenance of the hidden variables.

Use the client IP address.
  This doesn't work very well, because an IP address may be shared by
  many clients.

Data Storage
============

Data can be simply stored in the object database. This provides lots
of flexibility. You can store pretty much anything you want as long as
it is persistent. You get the full benefit of the object database,
such as transactions, transparency, clustering, and so on. Using the
object database is especially useful when:

- Writes are infrequent

- Data are complex

If writes are frequent, then the object database introduces
scalability problems. Really, any transactional database is likely to
introduce problems with frequent writes. If you are tempted to update
session data on every request, think very hard about it. You are
creating a scalability problem.

If you know that scalability is not (and never will be) an issue,
you can just use the object database.

If you have client data that needs to be updated often (as in every
request), consider storing the data on the client. (Like all data
received from a client, it may be tainted and, in most instances,
should not be trusted. Sensitive information that the user should not
see should likewise not be stored on the client, unless encrypted with
a key the client has no access to.) If you can't store it on the
client, then consider some other storage mechanism, like a fast
database, possibly without transaction support.

You may be tempted to store session data in memory for speed. This
doesn't turn out to work very well. If you need scalability, then you
need to be able to use an application-server cluster and storage of
session data in memory defeats that. You can use "server-affinity" to
assure that requests from a client always go back to the same server,
but not all load balancers support server affinity, and, for those
that do, enabling server affinity tends to defeat load balancing.

Session Expiration
==================

You may wish to ensure that sessions terminate after some period of
time. This may be for security reasons, or to avoid accidental sharing
of a session among multiple clients. The policy might be expressed in
terms of total session time, or maximum inactive time, or some
combination.

There are a number of ways to approach this. You can expire client
identifiers. You can expire session data.

Data Expiration
===============

Because HTTP is a stateless protocol, you can't tell whether a user is
thinking about a task or has simply stopped working on it. Some means
is needed to free server session storage that is no-longer needed.

The simplest strategy is to never remove data. This strategy has some
obvious disadvantages. Other strategies can be viewed as optimizations
of the basic strategy. It is important to realize that a data
expiration strategy can be informed by, but need not be constrained by
a session-expiration strategy.
